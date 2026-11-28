"""Discover published match reports and archive nominal lineup minutes in bounded batches."""

import argparse
import datetime as dt
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from ex_history_archive import atomic_write, utc
from ex_official_calendar import slovak_fixtures, ukrainian_results_and_fixtures
from ex_official_minutes import minutes_from_timeline
from ex_official_report_html import plain, slovak_minutes, ukrainian_minutes
from run_ex_official_minutes_batch import parse_parenthetical_lineup
from run_ex_official_sources import capture, read_evidence

CALENDARS = {
    "sk": "https://www.nikeliga.sk/zapasy/2026?id_round=999&id_stage=1",
    "cz": "https://www.chanceliga.cz/zapasy",
    "ua": "https://upl.ua/en/tournaments/games",
}


def report_links(league, page, source, cutoff):
    if league == "sk":
        for match_id, date, _, names, _, link, _ in slovak_fixtures(page):
            if dt.datetime.strptime(date, "%d.%m.%Y").date() < cutoff:
                yield match_id, urljoin(source, link), date, names
    elif league == "ua":
        for row, score in ukrainian_results_and_fixtures(page):
            match_id, date, _, names, _, link, _ = row
            if score is not None and dt.datetime.strptime(date, "%d.%m.%Y").date() < cutoff:
                yield match_id, urljoin(source, link + "/report"), date, names
    else:
        # The canonical full-slug statistics link is discovered in the report.
        for link, match_id in re.findall(r'href="(/zapas/(\d+)-[a-z0-9-]+)"', page):
            yield match_id, urljoin(source, link), None, None


def czech_minutes(page, match_id):
    if not re.search(rf'href="/zapas/statistiky/{match_id}-[a-z0-9-]+(?:#tab)?"', page):
        raise ValueError("Missing canonical Chance Liga report identity")
    if re.search(r'<i[^>]*class="[^"]*ico-card[^"]*\bred\b', page, re.I):
        raise ValueError("Dismissals require reviewed nominal representation")
    paragraphs = re.findall(r'<p(?:\s[^>]*)?>\s*<strong>([^<]+):</strong>(.*?)</p>', page, re.S)
    lineup = [(plain(name), plain(text).split(". Trenér:", 1)[0])
              for name, text in paragraphs if ". Trenér:" in unescape(text)]
    if len(lineup) != 2:
        raise ValueError("Expected two completed Chance Liga match report lineups")
    return [group[0] for group in lineup], {
        side: minutes_from_timeline(*parse_parenthetical_lineup(group[1]))
        for side, group in zip(("home", "away"), lineup, strict=True)}


def collect(root, limit, offset=0):
    boards = capture(CALENDARS, root / "calendars")
    plans, issues = {}, {}
    for league, entry in boards.items():
        try:
            page = read_evidence(root / "calendars", entry)
            as_of = utc(entry["captured_at"]).date()
            observed = {}
            for match_id, url, day, names in report_links(league, page, entry["final_url"], as_of):
                observed.setdefault(match_id, (url, day, names))
            if not observed:
                raise ValueError("No official report links")
            plans[league] = observed
        except (KeyError, OSError, ValueError) as exc:
            issues[league] = str(exc)
    selected = {f"{league}-{match_id}": (league, match_id, *entry)
                for league, rows in plans.items()
                for match_id, entry in list(rows.items())[offset:offset+limit]}
    reports = capture({label: row[2] for label, row in selected.items()}, root / "reports", reuse=True)
    result = {}
    for label, (league, match_id, url, day, names) in selected.items():
        try:
            evidence = reports[label]
            if evidence.get("final_url") != url:
                raise ValueError(evidence.get("error", "Unexpected official report redirect"))
            page = read_evidence(root / "reports", evidence)
            if league == "cz":
                names, minutes = czech_minutes(page, match_id)
            else:
                minutes = (slovak_minutes if league == "sk" else ukrainian_minutes)(page)
        except (KeyError, OSError, ValueError) as exc:
            issues[label] = str(exc)
            continue
        result[label] = {"league": f"{league}.1", "official_match_id": match_id, "date_local": day,
                         "teams": dict(zip(("home", "away"), names, strict=True)),
                         "minutes": minutes, "source": evidence, "basis": "NOMINAL_REGULATION"}
    return {"reports": result, "discovered": {league: len(rows) for league, rows in plans.items()},
            "processed": len(selected), "issues": issues, "ex_final_allowed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--limit", type=int, choices=range(1, 21), default=5)
    p.add_argument("--offset", type=int, default=0)
    args = p.parse_args()
    if args.offset < 0:
        p.error("Offset must be nonnegative")
    report = collect(args.output, args.limit, args.offset)
    atomic_write(args.output / "minutes.json", (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({**report, "reports": list(report["reports"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
