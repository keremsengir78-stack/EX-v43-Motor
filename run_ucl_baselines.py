"""Compute provisional UCL research baselines from captured domestic evidence."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from ex_auto_control import auto_control
from ex_cross_verify import norm
from ex_decision import assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_engine import backtest, date
from ex_espn_provider import parse_espn_scoreboard
from ex_ucl_baseline import cross_league_baseline
from run_ucl_archive import full_time


CUTOFF = "2026-11-24"
FIXTURE_CONFIG = Path("config/ucl_matchday5_2026_research.json")


def verified_bytes(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"Source hash mismatch: {path}")
    return raw


def captured_rows(root):
    """Reparse raw snapshots. Report rows alone carry no source evidence."""
    archive = root / "openfootball"
    if (archive / "manifest.json").exists():
        for source in json.loads((archive / "manifest.json").read_text())["sources"]:
            if "error" in source or "season" not in source:
                continue
            league, season = source["league"], source["season"]
            raw = verified_bytes(archive / f"{season}_{league}.json", source["sha256"])
            for match in json.loads(raw)["matches"]:
                score = full_time(match)
                if (isinstance(score, list) and len(score) == 2
                        and all(type(goal) is int and 0 <= goal <= 30 for goal in score)
                        and match.get("date") and match["date"] < CUTOFF):
                    yield "openfootball", league, match["date"], match["team1"], match["team2"], *score

    shakhtar = Path(__file__).resolve().parent / "research/ucl/shakhtar-domestic.json"
    if shakhtar.exists():
        source = json.loads(shakhtar.read_text())
        for match in source["fixtures"]:
            if len({entry["url"] for entry in match["sources"]}) < 2:
                raise ValueError("Shakhtar result missing second source")
            score = match["score"]
            if len(score) != 2 or any(type(goal) is not int or not 0 <= goal <= 30 for goal in score):
                raise ValueError("Invalid Shakhtar score")
            yield "curated_club_results", source["league"], match["date"], match["home"], match["away"], *score

    domestic = root / "domestic"
    if (domestic / "report.json").exists():
        for source in json.loads((domestic / "report.json").read_text())["sources"]:
            if "error" in source or source.get("potentially_truncated"):
                continue
            raw = verified_bytes(domestic / (source["sha256"] + ".json"), source["sha256"])
            league = source["league"]
            for row in parse_espn_scoreboard(json.loads(raw), league, CUTOFF, source["date"]):
                yield "ESPN", league, row["date"], row["home"], row["away"], row["home_goals"], row["away_goals"]


def team_index(groups):
    leagues, aliases = {}, {}
    for league, teams in groups.items():
        for name, variants in teams.items():
            if name in leagues:
                raise ValueError(f"Club assigned to multiple leagues: {name}")
            leagues[name] = league
            for variant in [name, *variants]:
                key = league, norm(variant)
                if key in aliases and aliases[key] != name:
                    raise ValueError(f"Conflicting club alias: {variant} in {league}")
                aliases[key] = name
    return leagues, aliases


def season_year(league, day):
    return day.year - (league != "no.1" and day.month < 7)


def select_rows(records, aliases):
    groups = defaultdict(lambda: defaultdict(dict))
    for provider, league, day, home, away, hg, ag in records:
        day = date(day)
        if day >= date(CUTOFF):
            continue
        home, away = (aliases.get((league, norm(team)), norm(team)) for team in (home, away))
        key = day, home, away
        group = groups[league, season_year(league, day)][provider]
        row = dict(date=day, league=league, home=home, away=away, hg=hg, ag=ag)
        if key in group and group[key] != row:
            raise ValueError(f"Conflicting {provider} scores for {league} {key}")
        group[key] = row

    selected, coverage = [], []
    for (league, year), providers in sorted(groups.items()):
        # Keep seasons internally consistent. A partial daily capture cannot
        # displace a better-covered archive or duplicate its venue samples.
        primary = max(providers, key=lambda name: (len(providers[name]), name == "ESPN"))
        observed_scores = defaultdict(list)
        for source_rows in providers.values():
            for key, row in source_rows.items():
                observed_scores[key].append((row["hg"], row["ag"]))
        common = {key for key, scores in observed_scores.items() if len(scores) >= 2}
        conflicts = sorted(key for key in common if len(set(observed_scores[key])) > 1)
        selected.extend(row for key, row in providers[primary].items() if key not in conflicts)
        coverage.append({
            "league": league, "season_start_year": year, "provider": primary,
            "provider_rows": {name: len(rows) for name, rows in providers.items()},
            "exact_score_agreements": len(common) - len(conflicts),
            "excluded_score_conflicts": [
                {"date": day.isoformat(), "home": home, "away": away,
                 "scores": {name: [rows[day, home, away]["hg"], rows[day, home, away]["ag"]]
                            for name, rows in providers.items() if (day, home, away) in rows}}
                for day, home, away in conflicts
            ],
        })
    return sorted(selected, key=lambda row: (row["date"], row["league"], row["home"], row["away"])), coverage


def calculate_baselines(root, config):
    leagues, aliases = team_index(config["domestic_team_names"])
    rows, coverage = select_rows(captured_rows(root), aliases)
    results = []
    for fixture in config["fixtures"]:
        home, away = fixture["home"], fixture["away"]
        if home not in leagues or away not in leagues:
            results.append({"fixture": fixture, "status": "BLOCKED_TEAM_MAPPING", "ex_final_allowed": False})
            continue
        results.append(cross_league_baseline(
            rows, fixture, leagues[home], leagues[away], home, away, "2026-07-01", "2025-07-01",
        ))
    return rows, coverage, results


def audit_research_run(rows, results, leagues, fixture_report):
    """Exercise production decisions and gates without supplying unaudited features."""
    records = []
    market_keys = {"2.5_UST": "over25", "KG_VAR": "btts",
                   "MS1": "home_win", "MSX": "draw", "MS2": "away_win"}
    for result in results:
        fixture = result["fixture"]
        home, away = fixture["home"], fixture["away"]
        recomputed = cross_league_baseline(
            rows, fixture, leagues[home], leagues[away], home, away, "2026-07-01", "2025-07-01",
        ) if home in leagues and away in leagues else None
        baseline = result.get("baseline")
        gate_input = {
            "fixture": fixture,
            "status": "BASELINE_ONLY" if baseline else "INCOMPLETE",
            "recompute_consistent": result == recomputed,
            "fixture_lock": check_fixture(fixture, CUTOFF),
            "odds_lock": check_odds(None, fixture["kickoff_at"]),
            "market_baselines_pct": {key: round(baseline[value] * 100, 2)
                                     for key, value in market_keys.items()} if baseline else None,
        }
        records.append({
            "fixture": fixture, "decision_evidence": assess_markets({}, as_of=CUTOFF),
            "tur2_recompute_consistent": gate_input["recompute_consistent"],
            "fixture_lock": gate_input["fixture_lock"], "odds_lock": gate_input["odds_lock"],
            "auto_control": auto_control(gate_input), "ex_final_allowed": False,
        })
    return {
        "fixtures": records, "research_fixture_status": fixture_report.get("status"),
        "calibrated": False, "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest", action="store_true", help="Run chronological four-market baseline audit")
    args = parser.parse_args()
    root = Path("ucl_research_output")
    root.mkdir(exist_ok=True)
    config = json.loads(FIXTURE_CONFIG.read_text())
    rows, coverage, results = calculate_baselines(root, config)
    fixture_report_path = root / "fixture_verification.json"
    fixture_report = json.loads(fixture_report_path.read_text()) if fixture_report_path.exists() else {}
    leagues, _ = team_index(config["domestic_team_names"])
    audit = audit_research_run(rows, results, leagues, fixture_report)
    (root / "engine_gate_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    (root / "archive_baselines.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    (root / "domestic_coverage.json").write_text(json.dumps({
        "status": "PROVISIONAL_RESEARCH", "ex_final_allowed": False, "sources": coverage,
    }, ensure_ascii=False, indent=2))
    print("UCL_BASELINE_COUNTS", json.dumps({
        "rows": len(rows), "fixtures": len(results),
        "computed": sum(r["status"] == "UNCALIBRATED_CROSS_LEAGUE_BASELINE" for r in results),
    }))
    if args.backtest:
        evaluated = backtest(rows)
        (root / "domestic_baseline_backtest.json").write_text(json.dumps(evaluated, indent=2))
        print("UCL_DOMESTIC_BACKTEST", json.dumps(evaluated))
    for result in results:
        print("UCL_BASELINE_ROW", json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
