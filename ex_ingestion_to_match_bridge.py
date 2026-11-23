"""Bridge live-ingestion results to EX historical inputs without fabricating kickoffs.

The ingestion CSV contains dates, not verified UTC kickoff timestamps or
independent source observations. Missing fields must remain explicit blockers.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def prepare_ingested_records(rows, fixtures):
    if not isinstance(rows, list) or not isinstance(fixtures, list):
        raise ValueError("Expected results and fixtures lists")
    output = []
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("fixture_id"), str) or not fixture["fixture_id"].strip():
            raise ValueError("Each fixture needs a nonempty fixture_id")
        league = fixture.get("league")
        team = fixture.get("team")
        if not isinstance(league, str) or not isinstance(team, str) or not team.strip():
            raise ValueError("Each fixture needs league and team")
        historical = []
        issues = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Result row must be object")
            if row.get("league") != league or team not in (row.get("home"), row.get("away")):
                continue
            venue = "home" if team == row["home"] else "away"
            try:
                gf = int(row["home_goals"] if venue == "home" else row["away_goals"])
                ga = int(row["away_goals"] if venue == "home" else row["home_goals"])
                if gf < 0 or ga < 0:
                    raise ValueError("negative score")
            except (ValueError, TypeError, KeyError):
                issues.append("historical:invalid_score")
                continue
            historical.append({"fixture_key": [league, row.get("date"), row.get("home"), row.get("away")],
                               "venue": venue, "season": row.get("season"),
                               "goals_for": gf, "goals_against": ga,
                               "kickoff_at": None, "verified": False,
                               "source": row.get("source")})
        issues.extend(["kickoff_utc:missing", "independent_source_observations:missing"])
        if not historical:
            issues.append("historical:no_matching_records")
        output.append({"fixture_id": fixture["fixture_id"], "team": team,
                       "league": league, "historical_record_count": len(historical),
                       "historical_staging": historical,
                       "status": "BLOCKED_REQUIRES_VERIFIED_INPUT",
                       "issues": sorted(set(issues)), "ex_final_allowed": False})
    return {"fixture_count": len(output), "historical_records_staged":
            sum(r["historical_record_count"] for r in output),
            "blocked": len(output), "results": output,
            "ex_final_allowed": False,
            "note": "Date-only OpenFootball records cannot become verified UTC kickoff evidence."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results-csv", required=True, type=Path)
    p.add_argument("--fixtures-json", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    with a.results_csv.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    fixtures = json.loads(a.fixtures_json.read_text(encoding="utf-8"))
    report = prepare_ingested_records(rows, fixtures)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
