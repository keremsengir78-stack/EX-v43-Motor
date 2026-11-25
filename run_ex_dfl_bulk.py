"""Collect official Bundesliga matchday score evidence and compare the EX ledger."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from ex_history_archive import atomic_write
from ex_official_report_html import plain
from run_ex_official_sources import capture, read_evidence
from run_ex_source_audit import audit


DFL = "https://www.bundesliga.com/en/bundesliga/matchday"
TEAMS = {
    "1. FC Köln": "FC Koln", "1. FC Union Berlin": "Union Berlin",
    "1. FSV Mainz 05": "Mainz", "1. FC Heidenheim 1846": "Heidenheim",
    "Bayer 04 Leverkusen": "Leverkusen", "Borussia Dortmund": "Dortmund",
    "Borussia Mönchengladbach": "M'gladbach", "Eintracht Frankfurt": "Ein Frankfurt",
    "FC Augsburg": "Augsburg", "FC Bayern München": "Bayern Munich",
    "FC Schalke 04": "Schalke 04", "FC St. Pauli": "St Pauli",
    "Hamburger SV": "Hamburg", "Holstein Kiel": "Holstein Kiel",
    "RB Leipzig": "RB Leipzig", "SC Freiburg": "Freiburg",
    "SC Paderborn 07": "Paderborn", "SV 07 Elversberg": "Elversberg",
    "SV Elversberg": "Elversberg", "SV Werder Bremen": "Werder Bremen",
    "TSG Hoffenheim": "Hoffenheim", "VfB Stuttgart": "Stuttgart",
    "VfL Bochum 1848": "Bochum", "VfL Wolfsburg": "Wolfsburg",
}


def extract(page, source, captured_at):
    prefix = urlsplit(source).path + "/"
    captured = datetime.fromisoformat(captured_at)
    if captured.utcoffset() is None:
        raise ValueError("Evidence timestamp requires an offset")
    result, skipped = [], []
    template = (r'(<li\b(?:(?!</li>).)*?<score-bug\b.*?</score-bug>(?:(?!</li>).)*?</li>)'
                r'\s*<dfl-json-ld\b[^>]*>\s*<script type="application/ld\+json">(.*?)</script>')
    for card, markup in re.findall(template, page, re.S):
        event = json.loads(markup)
        link = urlsplit(event["url"])
        if (event.get("@type") != "SportsEvent" or link.netloc != "www.bundesliga.com"
                or not link.path.startswith(prefix) or not link.path.endswith("/liveticker")
                or link.path not in card):
            raise ValueError("Unmatched official fixture and score card")
        kickoff = datetime.fromisoformat(event["startDate"])
        day = kickoff.astimezone(ZoneInfo("Europe/Berlin")).date()
        if day >= captured.astimezone(ZoneInfo("Europe/Berlin")).date():
            continue
        scores = [plain(value) for value in re.findall(r'class="score">(.*?)</div>', card, re.S)]
        home, away = (event[side]["name"] for side in ("homeTeam", "awayTeam"))
        if home not in TEAMS or away not in TEAMS or len(scores) != 2 or not all(s.isdecimal() for s in scores):
            skipped.append({"source": event["url"], "teams": [home, away], "scores": scores})
            continue
        result.append({"date": day.isoformat(), "home": TEAMS[home], "away": TEAMS[away],
                       "official_score": list(map(int, scores)), "source": event["url"]})
    if not result:
        raise ValueError("No supported official score cards")
    return result, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = {f"dfl-{season}-{round_number}": f"{DFL}/{season}-{season+1}/{round_number}"
               for season, rounds in ((2025, 34), (2026, 10)) for round_number in range(1, rounds+1)}
    root = args.output / "raw"
    manifest = capture(sources, root)
    matches, skipped, errors = [], [], {}
    for key, entry in manifest.items():
        try:
            if entry.get("url") != entry.get("final_url"):
                raise ValueError(entry.get("error", "Unexpected official redirect"))
            parsed, unknown = extract(read_evidence(root, entry), entry["final_url"], entry["captured_at"])
            matches.extend(parsed)
            skipped.extend(unknown)
        except (OSError, ValueError, KeyError) as exc:
            errors[key] = str(exc)
    prior = json.loads(Path("research/ucl/dfl-score-review.json").read_text())
    expected = {tuple(row) for row in prior["fixtures"]}
    actual = {(row["date"], row["home"], row["away"], *row["official_score"]) for row in matches}
    if not expected <= actual:
        raise ValueError(f"Official parser disagrees with reviewed pilot: {expected - actual}; {errors}")
    report = audit(json.loads(args.ledger.read_text()), {"fixtures": matches})
    for name, data in (("audit", report), ("results", {"matches": matches, "skipped": skipped, "errors": errors})):
        atomic_write(args.output / f"{name}.json", (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"parsed": len(matches), "skipped": skipped, "errors": errors, "audit": report["counts"]}))


if __name__ == "__main__":
    main()
