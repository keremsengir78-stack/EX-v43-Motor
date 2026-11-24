"""Collect dated ESPN score evidence for both main EX verification queues."""

import argparse
import json
from collections import Counter
from itertools import zip_longest
from pathlib import Path

from ex_cross_verify import norm, reconcile_staged_with_third
from ex_engine import load
from ex_espn_provider import ESPN_LEAGUES, parse_espn_scoreboard
from ex_history_archive import BudgetExhausted, HistoryArchive, atomic_write, paced_download, source_error
from ex_history_sources import ESPN


def history_queue(audit, results):
    pending = {(block["season"], block["league"], row["date"], row["home"], row["away"])
               for block in audit["secondary_audits"] for row in block["comparison"]["unmatched_details"]}
    history = [{"season": r["season"], "date": str(r["date"]), "league": r["league"],
                "home": r["home"], "away": r["away"], "home_goals": r["hg"], "away_goals": r["ag"]}
               for r in results
               if (r["season"], r["league"], str(r["date"]), r["home"], r["away"]) in pending]
    if len(history) != len(pending):
        raise ValueError("Historical audit queue and result files differ")
    return history


def league_scoreboard(raw, league, day, as_of):
    payload = json.loads(raw)
    leagues = {item.get("slug") for item in payload["leagues"]}
    if leagues != {ESPN_LEAGUES[league]}:
        raise ValueError("ESPN scoreboard competition mismatch")
    return parse_espn_scoreboard(payload, league, as_of, day)


def collect_scores(queues, as_of, aliases, archive):
    # Alternate between the two queues, then request each league/date only once.
    days_by_queue = [sorted({(r["date"], r["league"]) for r in rows if r["date"] < as_of}, reverse=True)
                     for rows in queues.values()]
    days = dict.fromkeys(day for group in zip_longest(*days_by_queue) for day in group if day is not None)
    sources, errors, scores = {}, [], []
    deferred = 0
    for day, league in days:
        url = f"{ESPN}/{ESPN_LEAGUES[league]}/scoreboard?dates={day.replace('-', '')}"
        try:
            rows, metadata = archive.get(
                url, lambda raw, _: league_scoreboard(raw, league, day, as_of),
                reusable=bool,
            )
        except BudgetExhausted:
            deferred += 1
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(source_error("scoreboard", url, exc))
        else:
            sources[day, league] = metadata
            scores.extend(rows)
    reports = {}
    for name, queue in queues.items():
        result = reconcile_staged_with_third(queue, scores, as_of, aliases)
        reports[name] = {
            "queued": len(queue),
            "provisional_matches": [{**r, "source": sources[r["date"], r["league"]]}
                                    for r in result["verified"]],
            "conflicts": [{**r, "source": sources[r["date"], r["league"]]} for r in result["conflicts"]],
            "unresolved": result["unresolved"],
        }
    return {"queues": reports, "date_requests": len(days), "requests": archive.requests,
            "cache_hits": archive.cache_hits, "deferred_dates": deferred, "errors": errors,
            "source_failure_counts": dict(Counter(item["category"] for item in errors)),
            "source_references": list(sources.values()), "provenance": "PENDING_INDEPENDENCE_AUDIT",
            "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--aliases", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=100, choices=range(1, 501), metavar="1..500")
    args = parser.parse_args()
    audit = json.loads((args.data / "audit.json").read_text())
    queues = {"historical": history_queue(audit, load(args.data / "results.csv")),
              "newer": json.loads((args.data / "secondary_only_unverified.json").read_text())}
    aliases = {league: {norm(k): value for k, value in names.items()}
               for league, names in json.loads(args.aliases.read_text()).items()}
    report = collect_scores(queues, args.as_of, aliases,
                            HistoryArchive(args.cache, args.budget, fetch=paced_download(.75)))
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({**{k: report[k] for k in ("date_requests", "requests", "cache_hits", "deferred_dates",
                                               "source_failure_counts")},
                      "queues": {k: {field: len(v) if isinstance(v, list) else v for field, v in queue.items()}
                                 for k, queue in report["queues"].items()}}))


if __name__ == "__main__":
    main()
