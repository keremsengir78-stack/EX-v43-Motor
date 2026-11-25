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
from ex_official_report_html import slovak_minutes, ukrainian_minutes
from ex_pfl_protocol import extract_minutes, pdf_layout
from run_ex_official_minutes_batch import OFFICIAL_HOSTS, normalize


ALLOWED = frozenset().union(*OFFICIAL_HOSTS.values(), {"www.bundesliga.com", "sabahfc.az", "www.laliga.com",
                                                  "en.legaseriea.it", "fantasy.premierleague.com", "www.om.fr"})


def checked(url):
    address = urlsplit(url)
    if address.scheme != "https" or address.netloc not in ALLOWED or address.fragment:
        raise ValueError("Unregistered official evidence URL")


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def capture(config, root, *, reuse=False):
    client = build_opener(OfficialRedirect)
    manifest = root / "manifest.json"
    previous = json.loads(manifest.read_text()) if reuse and manifest.is_file() else {}
    rows = {}
    requested = False
    for name, url in config.items():
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("Invalid source label")
        try:
            checked(url)
            old = previous.get(name, {})
            if old.get("url") == url and old.get("sha256"):
                try:
                    checked(old["final_url"])
                    read_bytes(root, old)
                except (ValueError, OSError, KeyError):
                    pass
                else:
                    rows[name] = old
                    continue
            if requested:
                time.sleep(0.75)
            requested = True
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
    atomic_write(root / "manifest.json", (json.dumps({**previous, **rows}, indent=2) + "\n").encode())
    return rows


def read_bytes(root, entry):
    digest = entry["sha256"]
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Malformed evidence digest")
    raw = (root / f"{digest}.html").read_bytes()
    if len(raw) != entry["bytes"] or sha256(raw).hexdigest() != digest:
        raise ValueError("Evidence bytes do not match manifest")
    return raw


def read_evidence(root, entry):
    return read_bytes(root, entry).decode("utf-8")


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


def parse_minutes_batch(root, fixtures):
    """Resolve match reports from immutable evidence and record partial coverage."""
    manifest = json.loads((root / "manifest.json").read_text())
    matches, errors, seen = [], {}, set()
    for label, fixture in fixtures.items():
        try:
            league = fixture["league"]
            entry = manifest[label]
            source = urlsplit(fixture["source"])
            is_pdf = league == "az.1" and re.fullmatch(
                r"/storage/games/files/[a-f0-9]+_\d+\.pdf", source.path) is not None
            id_field = "official_document_id" if is_pdf else "official_match_id"
            key = league, fixture[id_field]
            if (source.hostname not in OFFICIAL_HOSTS[league] or key in seen
                    or not key[1].isascii() or not key[1].isdigit()
                    or not re.search(rf"(?<![0-9]){key[1]}(?![0-9])", source.path)
                    or entry["url"] != fixture["source"] or entry["final_url"] != fixture["source"]):
                raise ValueError("Mismatch or duplicate official match identity")
            seen.add(key)
            if is_pdf:
                minutes = extract_minutes(pdf_layout(read_bytes(root, entry)), fixture["home"],
                                          fixture["away"], fixture["match_date_label"])
            elif league == "cz.1":
                page = read_evidence(root, entry)
                reviewed = extract_czech_report(page, fixture, fixture["labels"])
                if reviewed["errors"]:
                    raise ValueError(str(reviewed["errors"]))
                minutes = reviewed["minutes"][0]["minutes"]
            elif league == "ua.1":
                minutes = ukrainian_minutes(read_evidence(root, entry))
            elif league == "sk.1":
                minutes = slovak_minutes(read_evidence(root, entry))
            else:
                raise ValueError("No supported PFL match document in the public HTML response")
            matches.append({"league": league, id_field: key[1],
                            "source": entry, "minutes": minutes, "basis": "NOMINAL_REGULATION"})
        except (KeyError, AttributeError, TypeError, OSError, ValueError) as exc:
            errors[label] = str(exc)
    return {"matches": matches, "errors": errors, "ex_final_allowed": False}


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
            try:
                html = read_evidence(root, entry)
            except (OSError, ValueError):
                html = ""
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
    parser.add_argument("--minutes-fixtures", type=Path)
    args = parser.parse_args()
    print(json.dumps(capture(json.loads(args.config.read_text()), args.output)))
    if args.minutes_fixtures:
        result = parse_minutes_batch(args.output, json.loads(args.minutes_fixtures.read_text()))
        atomic_write(args.output / "minutes.json", (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
        print(json.dumps({"minutes_matches": len(result["matches"]), "errors": result["errors"]}))


if __name__ == "__main__":
    main()
