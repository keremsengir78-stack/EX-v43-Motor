"""Bounded HTTP collection with replayable content hashes and restart checkpoints."""

import datetime as dt
import hashlib
from http.client import IncompleteRead
import json
import os
import tempfile
import urllib.request
from urllib.error import HTTPError, URLError
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit


HOSTS = {"site.api.espn.com", "www.uefa.com", "archive-api.open-meteo.com", "api.open-meteo.com", "power.larc.nasa.gov", "api.openligadb.de"}
HOSTS.update({
    "fantasy.premierleague.com", "en.legaseriea.it", "www.laliga.com", "www.bundesliga.com",
    "www.knvb.nl", "www.om.fr", "www.tff.org", "www.ligaportugal.pt", "www.proleague.be", "www.eliteserien.no",
})
MAX_BYTES = 5_000_000


def utc(value):
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() != dt.timedelta(0):
        raise ValueError("UTC timestamp required")
    return stamp


def checked_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in HOSTS or parsed.fragment:
        raise ValueError("Unsupported evidence source URL")


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url):
    checked_url(url)
    client = urllib.request.build_opener(RestrictedRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "EX-history-collector/1.0"})
    with client.open(request, timeout=15) as response:
        try:
            raw = response.read(MAX_BYTES + 1)
        except IncompleteRead as exc:
            raise OSError("Incomplete HTTP response body") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("Evidence exceeds maximum size")
    return raw


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        name = temporary.name
        temporary.write(data)
    try:
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class BudgetExhausted(Exception):
    pass


class HistoryArchive:
    def __init__(self, directory, budget, fetch=download, clock=None):
        self.root = Path(directory)
        self.budget = budget
        self.fetch = fetch
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.requests = 0
        self.cache_hits = 0

    @staticmethod
    def digest(raw):
        return hashlib.sha256(raw).hexdigest()

    def _record(self, url, raw, captured):
        digest = self.digest(raw)
        metadata = {"url": url, "retrieved_at": captured.isoformat(), "sha256": digest, "size": len(raw)}
        atomic_write(self.root / "raw" / digest, raw)
        canonical = json.dumps(metadata, sort_keys=True).encode()
        key = self.digest(url.encode())
        atomic_write(self.root / "captures" / key / (self.digest(canonical) + ".json"), canonical)
        pointer = self.root / "index" / (key + ".json")
        if not pointer.exists() or captured >= utc(json.loads(pointer.read_text())["retrieved_at"]):
            atomic_write(pointer, canonical)
        return metadata

    def _load(self, metadata, url):
        captured = utc(metadata["retrieved_at"])
        if metadata["url"] != url or captured > self.clock():
            raise ValueError("Invalid cache source or capture time")
        digest = metadata["sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid evidence SHA-256")
        raw = (self.root / "raw" / digest).read_bytes()
        if self.digest(raw) != digest or len(raw) != metadata["size"]:
            raise ValueError("Cached source integrity check failed")
        return raw, captured

    def prior_capture(self, url, before):
        """Return the most recent captured source strictly before the cutoff."""
        checked_url(url)
        directory = self.root / "captures" / self.digest(url.encode())
        metadata = [json.loads(path.read_text()) for path in directory.glob("*.json")]
        eligible = [item for item in metadata if utc(item["retrieved_at"]) < before]
        if not eligible:
            return None
        item = max(eligible, key=lambda row: utc(row["retrieved_at"]))
        raw, captured = self._load(item, url)
        self.cache_hits += 1
        return raw, captured, item

    def import_capture(self, url, raw, captured, expected_sha):
        checked_url(url)
        if captured > self.clock() or len(raw) > MAX_BYTES or self.digest(raw) != expected_sha:
            raise ValueError("Invalid imported snapshot time, size or hash")
        return self._record(url, raw, captured)

    def get(self, url, parse, *, max_age=None, reusable=lambda value: True, content_schema=None):
        checked_url(url)
        pointer = self.root / "index" / (self.digest(url.encode()) + ".json")
        if pointer.exists():
            metadata = json.loads(pointer.read_text())
            raw, captured = self._load(metadata, url)
            value = parse(raw, captured)
            if (max_age is None or self.clock() - captured < max_age) and reusable(value):
                self.cache_hits += 1
                return value, metadata
        if self.requests >= self.budget:
            raise BudgetExhausted()
        failure = self.root / "failures" / pointer.name
        host_pause = self.root / "rate_limits" / urlsplit(url).hostname
        for checkpoint_path in (host_pause, failure):
            if checkpoint_path.exists():
                checkpoint = json.loads(checkpoint_path.read_text())
                content_updated = (
                    checkpoint_path == failure
                    and checkpoint.get("category") == "INVALID_SOURCE_CONTENT"
                    and content_schema is not None
                    and checkpoint.get("content_schema") != content_schema
                )
                retry_at = utc(checkpoint["retry_after"])
                if checkpoint.get("category") == "TRANSPORT" and "failed_at" not in checkpoint:
                    # Old archives used a fixed one-hour transport delay.
                    retry_at -= dt.timedelta(minutes=55)
                if not content_updated and retry_at > self.clock():
                    raise RetryDeferred(checkpoint)
        self.requests += 1
        try:
            raw = self.fetch(url)
            captured = self.clock()
            value = parse(raw, captured)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            category = failure_class(exc)
            delay = (dt.timedelta(minutes=5) if category == "TRANSPORT"
                     else dt.timedelta(hours=24 if category in {"ACCESS_DENIED", "NOT_AVAILABLE"} else 1))
            now = self.clock()
            retry_at = retry_after(exc, now, delay)
            checkpoint = {"error": str(exc), "category": category, "retry_after": retry_at.isoformat(),
                          "content_schema": content_schema, "failed_at": now.isoformat()}
            encoded = json.dumps(checkpoint).encode()
            atomic_write(failure, encoded)
            if category == "RATE_LIMIT":
                atomic_write(host_pause, encoded)
            raise
        failure.unlink(missing_ok=True)
        return value, self._record(url, raw, captured)


def retry_after(exc, now, delay):
    default = now + delay
    if not isinstance(exc, HTTPError) or exc.code not in (429, 503) or not exc.headers:
        return default
    value = exc.headers.get("Retry-After", "").strip()
    try:
        if value.isdecimal():
            requested = now + dt.timedelta(seconds=int(value))
        else:
            requested = parsedate_to_datetime(value)
        return max(default, requested)
    except (OverflowError, TypeError, ValueError):
        return default


class RetryDeferred(ValueError):
    def __init__(self, checkpoint):
        super().__init__(f"Source retry deferred: {checkpoint['error']}")
        self.checkpoint = checkpoint


def failure_class(exc):
    if isinstance(exc, RetryDeferred):
        return exc.checkpoint.get("category", "RETRY_DEFERRED")
    if isinstance(exc, HTTPError):
        if exc.code in (401, 403):
            return "ACCESS_DENIED"
        if exc.code == 429:
            return "RATE_LIMIT"
        if exc.code in (404, 410):
            return "NOT_AVAILABLE"
        return "UPSTREAM_HTTP" if exc.code >= 500 else "REQUEST_REJECTED"
    if isinstance(exc, URLError) and "403" in str(exc.reason):
        return "ACCESS_DENIED"
    if isinstance(exc, OSError):
        return "TRANSPORT"
    return "INVALID_SOURCE_CONTENT"


def source_error(stage, url, exc):
    return {"stage": stage, "url": url, "category": failure_class(exc),
            "retry_deferred": isinstance(exc, RetryDeferred), "error": str(exc)}


def paced_download(interval):
    """Limit start-to-start source request rate for a single worker."""
    import time

    next_request = 0.0

    def fetch(url):
        nonlocal next_request
        time.sleep(max(0, next_request - time.monotonic()))
        next_request = time.monotonic() + interval
        return download(url)

    return fetch
