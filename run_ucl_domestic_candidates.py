"""Capture alternate domestic sources in quarantine for fixture-level review."""

import csv
import datetime as dt
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path


SOURCES = (
    ("cz.1", "OpenFootball", "Slavia Praha",
     "https://raw.githubusercontent.com/openfootball/europe/6461b7b60a8d515bd60dd9323ca67c271b011ad3/czech-republic/2026-27_cz1.txt"),
    ("ua.1", "Soccerway via open-matchday", "Shakhtar Donetsk",
     "https://raw.githubusercontent.com/oladeeayo/open-matchday/96677da89111985ef0b445ba45012b00d60d0490/data/UKR_1_premier-league/results_2627.csv"),
)
CUTOFF = "2026-11-24"


def czech_rows(text):
    day = None
    for line in text.splitlines():
        heading = re.fullmatch(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2} \d{1,2})(?: (\d{4}))?", line)
        if heading:
            month_day, year = heading.groups()
            if not year:
                year = "2026" if month_day[:3] in {"Jul", "Aug", "Sep", "Oct", "Nov", "Dec"} else "2027"
            day = dt.datetime.strptime(f"{month_day} {year}", "%b %d %Y").date().isoformat()
            continue
        match = re.fullmatch(r"\s+(?:\d{2}:\d{2}\s+)?(\S.*?)\s{2,}(\d{1,2})-(\d{1,2})\s+\(\d+-\d+\)\s{2,}(\S.*?)\s*", line)
        if match and day:
            home, hg, ag, away = match.groups()
            yield day, home, away, int(hg), int(ag)


def ukraine_rows(text):
    for row in csv.DictReader(io.StringIO(text)):
        if row["source"] != "soccerway":
            raise ValueError("Unexpected upstream result source")
        for goal in ("ft_home", "ft_away"):
            if not re.fullmatch(r"[0-9]{1,2}", row[goal]):
                raise ValueError("Invalid Soccerway full-time score")
        yield dt.date.fromisoformat(row["date"]).isoformat(), row["home"], row["away"], int(row["ft_home"]), int(row["ft_away"])


def main():
    root = Path("ucl_research_output/domestic_candidates")
    root.mkdir(parents=True, exist_ok=True)
    reports = []
    for league, provider, club, url in SOURCES:
        report = {"league": league, "provider": provider, "club": club, "url": url}
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Candidate archive exceeds size limit")
            parser = czech_rows if league == "cz.1" else ukraine_rows
            rows = [row for row in parser(raw.decode("utf-8-sig")) if "2026-07-01" <= row[0] < CUTOFF]
            if not rows or len({row[:3] for row in rows}) != len(rows) or any(max(row[3:]) > 30 for row in rows):
                raise ValueError("Empty, duplicate or invalid candidate results")
            filename = f"{league}.raw"
            (root / filename).write_bytes(raw)
            team_rows = [row for row in rows if club in row[1:3]]
            report.update(
                status="UNVERIFIED_CANDIDATES", sha256=hashlib.sha256(raw).hexdigest(), file=filename,
                retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                league_rows=len(rows), team_home=sum(row[1] == club for row in team_rows),
                team_away=sum(row[2] == club for row in team_rows), team_rows=team_rows,
            )
        except (OSError, ValueError, KeyError) as exc:
            report.update(status="SOURCE_ERROR", error=str(exc))
        reports.append(report)
    result = {"sources": reports, "independently_verified": False, "ex_final_allowed": False}
    (root / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print("UCL_DOMESTIC_CANDIDATES", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
