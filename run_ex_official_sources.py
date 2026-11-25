"""Capture bounded, immutable official league evidence for offline parsing."""

import argparse
import datetime as dt
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ex_history_archive import MAX_BYTES, atomic_write
from run_ex_official_minutes_batch import OFFICIAL_HOSTS, normalize


ALLOWED = frozenset().union(*OFFICIAL_HOSTS.values(), {"www.bundesliga.com", "sabahfc.az"})


def checked(url):
    address = urlsplit(url)
    if address.scheme != "https" or address.netloc not in ALLOWED or address.fragment:
        raise ValueError("Unregistered official evidence URL")


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def capture(config, root):
    client = build_opener(OfficialRedirect)
    rows = {}
    for index, (name, url) in enumerate(config.items()):
        if index:
            time.sleep(0.75)
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("Invalid source label")
        try:
            checked(url)
            with client.open(Request(url, headers={"User-Agent": "EX-v4.3 evidence audit"}), timeout=12) as response:
                raw = response.read(MAX_BYTES + 1)
                final_url = response.geturl()
                checked(final_url)
            if len(raw) > MAX_BYTES or not raw:
                raise ValueError("Invalid official evidence size")
            digest = sha256(raw).hexdigest()
            atomic_write(root / f"{digest}.html", raw)
        except (URLError, OSError, ValueError) as exc:
            rows[name] = {"url": url, "error": str(exc)}
        else:
            rows[name] = {"url": url, "final_url": final_url, "sha256": digest,
                          "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                          "bytes": len(raw)}
    atomic_write(root / "manifest.json", (json.dumps(rows, indent=2) + "\n").encode())
    return rows


def read_evidence(root, entry):
    digest = entry["sha256"]
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Malformed evidence digest")
    raw = (root / f"{digest}.html").read_bytes()
    if len(raw) != entry["bytes"] or sha256(raw).hexdigest() != digest:
        raise ValueError("Evidence bytes do not match manifest")
    return raw.decode("utf-8")


def extract_czech_report(html, fixture, labels):
    """Read both actual Chance Liga report paragraphs for an identified fixture."""
    paragraphs = re.findall(r"<p(?:\s[^>]*)?>\s*<strong>([^<]+):</strong>(.*?)</p>",
                            html, flags=re.IGNORECASE | re.DOTALL)
    teams = {}
    for side, label in labels.items():
        lines = [unescape(re.sub(r"<[^>]*>", "", value)) for name, value in paragraphs
                 if unescape(name).strip() == label]
        if len(lines) != 1 or ". Trenér:" not in lines[0]:
            raise ValueError(f"Missing or ambiguous official lineup for {side}")
        line = " ".join(lines[0].split(". Trenér:", 1)[0].split())
        teams[side] = {"lineup_text": line}
    return normalize([{**fixture, "teams": teams}])


ALTERNATE_CALENDARS = {
    "sk.1": ("https://www.nikeliga.sk/zapasy", r'href="/zapas/'),
    "ua.1": ("https://upl.ua/en/tournaments/games", r'href="/en/report/view/'),
    "az.1": ("https://sabahfc.az/?team_type=3", r"Sabah\s+vs|vs\s+Sabah"),
}


def archive_alternate_calendars(leagues, root):
    """Store alternative context without assigning an ESPN identity or a prediction."""
    sources = {league.replace(".", "-"): ALTERNATE_CALENDARS[league][0]
               for league in leagues if league in ALTERNATE_CALENDARS}
    if not sources:
        return {}
    manifests = capture(sources, root)
    results = {}
    for label, entry in manifests.items():
        league = label.replace("-", ".")
        status = "UNAVAILABLE"
        if "sha256" in entry:
            html = read_evidence(root, entry)
            if re.search(ALTERNATE_CALENDARS[league][1], html, re.IGNORECASE):
                status = "CLUB_CALENDAR_ARCHIVED" if league == "az.1" else "LEAGUE_CALENDAR_ARCHIVED"
            else:
                status = "FIXTURE_MARKUP_UNRECOGNIZED"
        results[league] = {"status": status, **entry}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(json.loads(args.config.read_text()), args.output)))


if __name__ == "__main__":
    main()
