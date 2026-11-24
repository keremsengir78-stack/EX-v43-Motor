"""Replay the completed archive without querying any upstream football source."""

import argparse
import json
from collections import Counter
from pathlib import Path

from ex_history_archive import HistoryArchive, atomic_write
from ex_history_sources import ESPN, match_detail
from ex_retrospective import EVIDENCE_CLASSES, build_examples, evaluate, settled_facts


def load_facts(plan, root):
    archives = [HistoryArchive(path.parent, 0) for path in root.glob("**/index")]
    archive_index = {}
    for archive in archives:
        for path in (archive.root / "index").glob("*.json"):
            meta = json.loads(path.read_text())
            archive_index.setdefault(meta["url"], []).append((archive, meta))
    facts, missing = [], 0
    for event in plan["pending_events"]:
        url = f"{ESPN}/{event['competition']}/summary?event={event['event_id']}"
        entries = archive_index.get(url)
        if not entries:
            missing += 1
            continue
        archive, meta = min(entries, key=lambda x: x[1]["retrieved_at"])
        def parse(raw, captured):
            detail = match_detail(raw, captured, event)
            fact = settled_facts(json.loads(raw), event, meta["retrieved_at"])
            totals = {}
            if not detail["roster_identity_conflicts"]:
                for team in event["teams"].values():
                    minutes = {
                        r["athlete_id"]: (r["provider_minutes"] if r["provider_minutes"] is not None
                                          else r["nominal_regulation_minutes"])
                        for r in detail["player_rows"] if r["team_id"] == team
                    }
                    if minutes and all(value is not None for value in minutes.values()) and sum(minutes.values()) == 990:
                        totals[team] = minutes
            return {**fact, "minutes": totals, "source_sha256": meta["sha256"]}
        parsed, _ = archive.get(url, parse)
        facts.append(parsed)
    return facts, missing


def deduplicate_scores(ledger):
    sources = {}
    for queue, data in ledger["queues"].items():
        candidates = {
            "ESPN": data["provisional_matches"],
            "OpenLigaDB": ledger.get("alternative_bundesliga", {}).get("queues", {}).get(queue, {}).get("verified", []),
        }
        for provider, rows in candidates.items():
            for row in rows:
                key = tuple(row[k] for k in ("league", "date", "home", "away"))
                score = (row["home_goals"], row["away_goals"])
                record = sources.setdefault(key, {"providers": set(), "scores": set(), "queues": set()})
                record["providers"].add(provider)
                record["scores"].add(score)
                record["queues"].add(queue)
    reviewed_keys = {}
    for group in ledger.get("reviewed_score_matches", {}).values():
        for kind, rows in group.items():
            for row in rows:
                key = tuple(row[k] for k in ("league", "date", "home", "away"))
                reviewed = reviewed_keys.setdefault(key, {"kinds": set(), "scores": set()})
                reviewed["kinds"].add(kind)
                reviewed["scores"].add((row["home_goals"], row["away_goals"]))
    summary = Counter(tuple(sorted(record["providers"])) for record in sources.values())
    disputed = sum(len((sources.get(key) or {}).get("scores", set())
                       | (reviewed_keys.get(key) or {}).get("scores", set())) > 1
                   for key in sources.keys() | reviewed_keys.keys())
    return {"unique_provider_matches": len(sources),
            "by_provider_combination": {"+".join(key): n for key, n in sorted(summary.items())},
            "unique_fixtures_including_reviewed": len(sources.keys() | reviewed_keys.keys()),
            "reviewed_fixtures_with_provider_match": len(sources.keys() & reviewed_keys.keys()),
            "conflicting_target_scores": disputed,
            "provider_overlap_proves_independence": False,
            "reviewed_evidence": {k: {name: len(rows) for name, rows in v.items()}
                                  for k, v in ledger.get("reviewed_score_matches", {}).items()},
            "lineage_status": {"ESPN": "UPSTREAM_MATCH_FEED_UNCONFIRMED",
                               "OpenLigaDB": "COMMUNITY_SOURCE_PER_MATCH_LINEAGE_UNCONFIRMED"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--score-ledger", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    facts, missing = load_facts(plan, args.archive)
    if not facts or args.require_complete and missing:
        raise ValueError(f"Archived match coverage incomplete: {len(facts)} available, {missing} missing")
    examples = build_examples(facts)
    report = {"provenance": "RETROSPECTIVE_SETTLED_EVENT_RECONSTRUCTION",
              "evidence_classes": EVIDENCE_CLASSES, "targets": len(plan["pending_events"]),
              "archived": len(facts), "missing": missing, "source_requests": 0,
              "terminal_evidence": dict(Counter(row.get("terminal_source", "UNUSABLE") for row in facts)),
              "feature_examples": len(examples), "markets": evaluate(examples),
              "production_calibration_allowed": False, "ex_final_allowed": False}
    if args.score_ledger:
        report["score_deduplication"] = deduplicate_scores(json.loads(args.score_ledger.read_text()))
    atomic_write(args.output, (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
