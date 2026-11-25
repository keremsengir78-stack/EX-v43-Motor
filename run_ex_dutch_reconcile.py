"""Reconcile the existing Eerste Divisie archive with KNVB score publications."""

import argparse
import csv
from datetime import date
import json
from pathlib import Path
import re

from ex_cross_verify import norm
from ex_history_archive import atomic_write
from ex_official_report_html import plain
from run_ex_official_sources import capture, read_evidence

VI = "https://www.vi.nl/competities/eerste-divisie/2025-2026/wedstrijden"
KNVB = "https://www.knvb.nl/competities/keuken-kampioen-divisie/uitslagen"
MONTHS = "januari februari maart april mei juni juli augustus september oktober november december".split()
ALIASES = {
    "ajaxamsterdamii": "jongajax", "azalkmaarii": "jongaz", "psveindhovenii": "jongpsv",
    "jongfcutrecht": "jongutrecht", "utrechtii": "jongutrecht", "psvii": "jongpsv",
    "ajaxii": "jongajax", "azii": "jongaz", "roda": "rodajc", "rodajckerkrade": "rodajc",
    "vitessearnhem": "vitesse", "vitesse": "vitesse", "toposs": "oss",
    "vvvvenlo": "vvv", "vvv": "vvv", "maastricht": "mvvmaastricht", "mvv": "mvvmaastricht",
}


def identity(day, home, away):
    clubs = [norm(name) for name in (home, away)]
    return (day, *(ALIASES.get(club, club) for club in clubs))


def parse_knvb(html, as_of):
    pattern = (r'(?=<span class="title"><span>\d{1,2} [a-z]+ \d{4}</span>)|'
               r'(?=<div class="row"><div class="value home">)')
    day, scores = None, {}
    for part in re.split(pattern, html):
        heading = re.match(r'<span class="title"><span>(\d{1,2}) ([a-z]+) (\d{4})</span>', part)
        if heading:
            day = date(int(heading[3]), 1 + MONTHS.index(heading[2]), int(heading[1]))
            continue
        if day is None or day >= as_of or not part.startswith('<div class="row">'):
            continue
        score = re.search(r'<div class="value center">\s*(\d{1,2})\s*-\s*(\d{1,2})\s*</div>', part)
        if not score:
            continue
        teams = re.findall(r'<div class="team">([^<]+)</div>', part)
        if len(teams) != 2:
            raise ValueError(f"Unexpected KNVB home-away structure on {day}")
        key = identity(day.isoformat(), *map(plain, teams))
        value = tuple(map(int, score.groups()))
        if key in scores or key[1] == key[2] or max(value) > 30:
            raise ValueError(f"Invalid or duplicate KNVB result {key}")
        scores[key] = value
    if not scores:
        raise ValueError("KNVB published no supported result rows")
    return scores


def parse_vi(html, as_of):
    results = {}
    anchors = re.findall(r'<a class="MatchList_match-link__[^"]+" href="/wedstrijden/'
                         r'(\d{4}-\d{2}-\d{2})/([a-z0-9-]+)-vs-([a-z0-9-]+)">(.*?)</a>', html, re.S)
    for day, home, away, block in anchors:
        if date.fromisoformat(day) >= as_of or not re.search(r">FT</span>", block):
            continue
        score = re.search(r'<ul class="score-element [^"]+">\s*<li>(\d{1,2})</li>\s*<li>(\d{1,2})</li>', block)
        if not score:
            continue
        team_list = re.search(r'<ul class="MatchList_teams__[^"]+">(.*?)</ul>', block, re.S)
        if team_list:
            names = [plain(cell) for cell in re.findall(r"<li\b[^>]*>(.*?)</li>", team_list[1], re.S)]
            if len(names) != 2 or not all(names):
                raise ValueError("VI result needs two rendered teams")
            home, away = names
        key = identity(day, home, away)
        value = tuple(map(int, score.groups()))
        if key in results and results[key] != value:
            raise ValueError(f"Conflicting VI result {key}")
        results[key] = value
    if not results:
        raise ValueError("VI published no supported completed score rows")
    return results



def parse_vi_daily(html, as_of):
    sections = re.split(r"<h2\b[^>]*>(.*?)</h2>", html, flags=re.S)
    matches = [sections[i + 1] for i in range(1, len(sections), 2)
               if plain(sections[i]) == "Keuken Kampioen Divisie"]
    if len(matches) != 1:
        raise ValueError("Daily VI page needs one exact Eerste Divisie section")
    return parse_vi(matches[0], as_of)


def reconcile(primary, results_by_source):
    output, counts = [], {}
    for row in primary:
        key = identity(row["date"], row["home"], row["away"])
        expected = int(row["home_goals"]), int(row["away_goals"])
        hits = {source: results[key] for source, results in results_by_source.items() if key in results}
        status = ("UNMATCHED" if not hits else
                  "MATCH" if all(result == expected for result in hits.values()) else "CONFLICT")
        counts[status] = counts.get(status, 0) + 1
        output.append({**row, "comparison": status, "comparison_scores": hits})
    return {"counts": counts, "fixtures": output, "result_sources": sorted(results_by_source),
            "upstream_lineage_certified": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--vi-daily-limit", type=int, choices=range(1, 151))
    args = parser.parse_args()
    sources = {"knvb": KNVB, "vi": VI}
    captures = capture(sources, args.output / "raw", reuse=True)
    results, issues = {}, {}
    for key, parse in (("knvb", parse_knvb), ("vi", parse_vi)):
        entry = captures[key]
        try:
            if entry.get("final_url") != sources[key]:
                raise ValueError(entry.get("error", "Unexpected Dutch source URL"))
            results[key] = parse(read_evidence(args.output / "raw", entry), args.as_of)
        except (OSError, KeyError, ValueError) as exc:
            issues[key] = str(exc)
    if "knvb" not in results:
        raise ValueError(issues.get("knvb", "Missing official Dutch result rows"))
    with args.primary.open() as source:
        primary = [row for row in csv.DictReader(source) if row["league"] == "nl.2"]
    if args.vi_daily_limit:
        covered = set().union(*(set(rows) for rows in results.values()))
        days = sorted({row["date"] for row in primary
                       if identity(row["date"], row["home"], row["away"]) not in covered}, reverse=True)
        daily = {day: f"https://www.vi.nl/wedstrijden/{day}" for day in days[:args.vi_daily_limit]}
        entries = capture(daily, args.output / "vi-daily", reuse=True)
        combined = {}
        for day, entry in entries.items():
            try:
                if entry.get("final_url") != daily[day]:
                    raise ValueError(entry.get("error", "Unexpected VI daily URL"))
                page = read_evidence(args.output / "vi-daily", entry)
                rows = parse_vi_daily(page, args.as_of)
                if any(key[0] != day for key in rows):
                    raise ValueError("Unexpected date in VI daily results")
                combined.update(rows)
            except (OSError, KeyError, ValueError) as exc:
                issues[f"vi-{day}"] = str(exc)
        results["vi-daily"] = combined
    result = reconcile(primary, results)
    result["source_evidence"] = captures
    result["source_issues"] = issues
    atomic_write(args.output / "comparison.json", (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode())
    by_day = {}
    for source_records in results.values():
        for day, home, away in source_records:
            by_day.setdefault(day, set()).add((home, away))
    unresolved = []
    for row in result["fixtures"]:
        if row["comparison"] == "UNMATCHED":
            day, home, away = identity(row["date"], row["home"], row["away"])
            possible = sorted(pair for pair in by_day.get(day, ()) if home == pair[0] or away == pair[1])
            unresolved.append({"date": day, "home": row["home"], "away": row["away"],
                               "same_day_same_side": possible})
    print(json.dumps({"reference_rows": len(primary), "source_rows": {source: len(rows) for source, rows in results.items()},
                      "counts": result["counts"], "source_issues": issues, "unresolved": unresolved}))


if __name__ == "__main__":
    main()
