"""Bounded HTTP collection with replayable content hashes and restart checkpoints."""

import datetime as dt
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


HOSTS = {"site.api.espn.com", "www.uefa.com"}
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
        raw = response.read(MAX_BYTES + 1)
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

    def get(self, url, parse, *, max_age=None, reusable=lambda value: True):
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
        if failure.exists():
            checkpoint = json.loads(failure.read_text())
            if utc(checkpoint["retry_after"]) > self.clock():
                raise ValueError(f"Source retry deferred: {checkpoint['error']}")
        self.requests += 1
        try:
            raw = self.fetch(url)
        except OSError as exc:
            checkpoint = {"error": str(exc), "retry_after": (self.clock() + dt.timedelta(hours=1)).isoformat()}
            atomic_write(failure, json.dumps(checkpoint).encode())
            raise
        captured = self.clock()
        value = parse(raw, captured)
        failure.unlink(missing_ok=True)
        return value, self._record(url, raw, captured)
