"""Reparse the official source probe and join the pending score queue."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from ex_daily_official import DUTCH, GERMANY, TURKEY_DETAIL, key, norway_scores, turkey_detail_scores, turkey_scores, uefa_scores
from ex_benelux_results import belgian_results, portuguese_results
from ex_history_archive import HistoryArchive, atomic_write
from run_ex_additional_official_scores import marseille_scores
from run_ex_dfl_bulk import extract as dfl_scores
from run_ex_dutch_reconcile import parse_knvb
from run_ex_laliga_bulk import extract as la_liga_scores
from run_ex_source_audit import audit


def source_rows(root):
    reports = json.loads((root / "report.json").read_text())
    for league, report in reports.items():
        archive = HistoryArchive(root / league, 0)
        observed = 0
        for source in report.get("sources", []):
            url = source["url"]
            raw, stamp = archive._load(source, url)
            if league in GERMANY:
                rows, _ = dfl_scores(raw.decode(), url, stamp.isoformat(),
                                     require_finished=True, allow_named_teams=True)
            elif league in DUTCH:
                rows = [{"date": day, "home": home, "away": away, "official_score": list(score)}
                        for (day, home, away), score in parse_knvb(raw.decode(), stamp.date()).items()]
            elif league == "es.1":
                rows, _ = la_liga_scores(raw.decode(), url, stamp.isoformat())
            elif league == "fr.1":
                rows = marseille_scores(raw.decode(), stamp.isoformat())
            elif league == "UCL":
                rows = uefa_scores(raw, url, stamp)
            elif league in {"be.1", "pt.1"}:
                parser = belgian_results if league == "be.1" else portuguese_results
                rows = parser(raw, url, stamp)
            elif league == "no.1":
                rows = norway_scores(raw, stamp)
            elif league == "tr.1":
                rows = turkey_detail_scores(raw, stamp) if url == TURKEY_DETAIL else turkey_scores(raw, stamp)
            else:
                raise ValueError(f"Unsupported league: {league}")
            observed += len(rows)
            for row in rows:
                yield {**row, "league": league, "raw_evidence": source}
        if observed != report["parsed_completed_rows"]:
            raise ValueError(f"Archived source replay count differs for {league}")


def reconcile(ledger, official):
    by_key = defaultdict(list)
    for items in audit(ledger)["categories"].values():
        for row in items:
            anchor = key(row["league"], row["date"], row["home"], row["away"])
            by_key[anchor].append(row)
    results = []
    counts = Counter()
    for row in official:
        anchor = key(row["league"], row["date"], row["home"], row["away"])
        candidates = by_key[anchor]
        scores = {tuple(score) for item in candidates for score in item["scores"]}
        paths = "AMBIGUOUS" if len(candidates) > 1 else "NOT_IN_QUEUE" if not candidates else (
            "SCORE_MATCH" if scores == {tuple(row["official_score"])} else "SCORE_CONFLICT")
        counts[paths] += 1
        results.append({**row, "queue_match": paths, "queue_scores": sorted(scores),
                        "lineage": "OFFICIAL_PUBLICATION_UPSTREAM_UNPROVEN"})
    return {"counts": dict(counts), "rows": results, "lineage_certified": 0, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reconcile(json.loads(args.ledger.read_text()), source_rows(args.probe))
    atomic_write(args.output, json.dumps(result, indent=2).encode())
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
