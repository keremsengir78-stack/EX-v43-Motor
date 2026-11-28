"""Compare the 75 staged scores with the captured ESPN result content."""

import json
from collections import Counter
from pathlib import Path

from ex_cross_verify import norm
from ex_espn_provider import parse_espn_scoreboard
from run_ucl_baselines import CUTOFF, verified_bytes

ALIASES = {
    "es.1": {
        "Deportivo Alavés": "Alavés", "Getafe CF": "Getafe",
        "RCD Espanyol de Barcelona": "Espanyol", "Levante UD": "Levante",
        "Club Atlético de Madrid": "Atlético Madrid", "Málaga CF": "Málaga",
        "Real Madrid CF": "Real Madrid", "Villarreal CF": "Villarreal",
        "Elche CF": "Elche", "CA Osasuna": "Osasuna", "Valencia CF": "Valencia",
    },
    "it.1": {
        "Frosinone Calcio": "Frosinone", "AC Monza": "Monza",
        "Udinese Calcio": "Udinese", "Cagliari Calcio": "Cagliari",
    },
}


def main():
    root = Path("ucl_research_output/domestic")
    queued = json.loads(Path("reports/external_2627_combined_75_candidate_queue.json").read_text())["fixtures"]
    groups = {(row["league"], row["date"]) for row in queued}
    snapshots = {}
    for source in json.loads((root / "report.json").read_text())["sources"]:
        if "error" in source or source.get("potentially_truncated"):
            continue
        key = source["league"], source["date"]
        if key not in groups:
            continue
        if key in snapshots:
            raise ValueError(f"Duplicate ESPN source date: {key}")
        sha = source["sha256"]
        raw = verified_bytes(root / f"{sha}.json", sha)
        snapshots[key] = parse_espn_scoreboard(json.loads(raw), key[0], CUTOFF, key[1]), source
    records = []
    for candidate in queued:
        league, day = candidate["league"], candidate["date"]
        aliases = ALIASES.get(league, {})
        lookup = [norm(aliases.get(candidate[side], candidate[side])) for side in ("home", "away")]
        rows, source = snapshots.get((league, day), ([], {}))
        matches = [row for row in rows if [norm(row["home"]), norm(row["away"])] == lookup]
        record = {
            key: candidate[key] for key in
            ("index", "league", "date", "home", "away", "reference_score", "provider")
        }
        record["status"] = "MISSING_OR_AMBIGUOUS"
        if len(matches) == 1:
            row, = matches
            score = [row["home_goals"], row["away_goals"]]
            record.update(
                status="ESPN_SCORE_MATCH" if score == candidate["reference_score"] == candidate["other_score"]
                else "ESPN_SCORE_CONFLICT",
                espn=row, espn_source={key: source[key] for key in ("sha256", "url", "retrieved_at")},
            )
        records.append(record)
    report = {
        "counts": dict(Counter(row["status"] for row in records)), "fixtures": records,
        "upstream_independence_certified": False, "ex_final_allowed": False,
    }
    target = Path("reports/external_2627_espn_content_reconciliation.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(report["counts"])


if __name__ == "__main__":
    main()
