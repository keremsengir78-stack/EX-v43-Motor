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


def reconcile(primary, results):
    output, counts = [], {}
    for row in primary:
        key = identity(row["date"], row["home"], row["away"])
        expected = int(row["home_goals"]), int(row["away_goals"])
        result = results.get(key)
        status = "UNMATCHED" if result is None else "MATCH" if result == expected else "CONFLICT"
        counts[status] = counts.get(status, 0) + 1
        output.append({**row, "comparison": status, "official_score": result})
    return {"counts": counts, "fixtures": output, "result_source": KNVB,
            "upstream_lineage_certified": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    entry = capture({"knvb": KNVB}, args.output / "raw", reuse=True)["knvb"]
    if entry.get("final_url") != KNVB:
        raise ValueError(entry.get("error", "Unexpected KNVB URL"))
    scores = parse_knvb(read_evidence(args.output / "raw", entry), args.as_of)
    with args.primary.open() as source:
        primary = [row for row in csv.DictReader(source) if row["league"] == "nl.2"]
    result = reconcile(primary, scores)
    result["source_evidence"] = entry
    atomic_write(args.output / "comparison.json", (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode())
    print(json.dumps({"reference_rows": len(primary), "official_rows": len(scores), "counts": result["counts"]}))


if __name__ == "__main__":
    main()
