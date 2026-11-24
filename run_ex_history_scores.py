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


def link_reviewed_scores(queues, directory, as_of):
    """Reuse audited records at their existing match-result scope."""
    from urllib.parse import urlsplit

    def key(row):
        return row["league"], row["date"], norm(row["home"]), norm(row["away"])

    def https(value):
        url = urlsplit(value)
        return url.scheme == "https" and bool(url.hostname) and not url.username and not url.password

    reviewed, independently_confirmed = {}, {}
    for path in sorted(directory.glob("official_verification_batch_*.json")):
        for row in json.loads(path.read_text())["records"]:
            if (row["official_verified"] is True and row["official_score"] == row["score"]
                    and https(row["official_source_url"])):
                match_key = key(row)
                if match_key in reviewed and reviewed[match_key]["score"] != row["score"]:
                    raise ValueError("Conflicting reviewed official results")
                reviewed[match_key] = {"score": row["score"], "source": row["official_source_url"],
                                       "evidence_file": path.as_posix()}
    path = directory / "independent_score_evidence_0001.json"
    for row in json.loads(path.read_text())["records"]:
        sources = [row[field] for field in ("source_1", "source_2", "source_3")]
        if (row["independent_score_verified"] is True and row["matched_score"] == row["independent_score"]
                and all(https(item["url"]) and item["score"] == row["independent_score"] for item in sources)
                and len({urlsplit(item["url"]).hostname for item in sources}) == 3):
            independently_confirmed[key(row)] = {"score": row["independent_score"], "sources": sources,
                                                 "evidence_file": path.as_posix()}
    result = {}
    for name, queue in queues.items():
        result[name] = {"official_result_matches": [], "independently_confirmed_result_matches": []}
        for row in queue:
            if row["date"] >= as_of:
                continue
            for field, evidence in (("official_result_matches", reviewed),
                                    ("independently_confirmed_result_matches", independently_confirmed)):
                item = evidence.get(key(row))
                if item and item["score"] == [row["home_goals"], row["away_goals"]]:
                    result[name][field].append({**row, **item, "scope": "MATCH_RESULT_ONLY"})
    return result


def alternative_scores(queues, as_of, aliases, archive):
    from ex_history_alternative_scores import OPENLIGA, bundesliga_scores

    snapshots, errors = {}, []
    scores = []
    seasons = sorted({int(row["season"].split("-")[0]) for rows in queues.values() for row in rows
                      if row["league"] == "de.1"})
    for year in seasons:
        url = f"{OPENLIGA}/{year}"
        try:
            rows, meta = archive.get(url, lambda raw, _: bundesliga_scores(raw, year, as_of),
                                     content_schema="openligadb-season-v1")
        except BudgetExhausted:
            raise ValueError("Alternative score budget smaller than requested Bundesliga seasons")
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(source_error("alternative_score", url, exc))
        else:
            scores.extend(rows)
            snapshots[year] = meta
    reports = {}
    for name, queue in queues.items():
        local = [row for row in queue if row["league"] == "de.1"]
        result = reconcile_staged_with_third(local, scores, as_of, aliases)
        reports[name] = {key: [{**row, "source": snapshots[int(row["season"].split("-")[0])]}
                               for row in result[key]] for key in ("verified", "conflicts")}
    return {"provider": "OpenLigaDB", "source_references": list(snapshots.values()), "errors": errors,
            "queues": reports, "independence_certified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--aliases", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=100, choices=range(1, 501), metavar="1..500")
    parser.add_argument("--alternative-bundesliga", action="store_true")
    args = parser.parse_args()
    audit = json.loads((args.data / "audit.json").read_text())
    queues = {"historical": history_queue(audit, load(args.data / "results.csv")),
              "newer": json.loads((args.data / "secondary_only_unverified.json").read_text())}
    aliases = {league: {norm(k): value for k, value in names.items()}
               for league, names in json.loads(args.aliases.read_text()).items()}
    from run_candidate_espn_reconciliation import ALIASES
    for league, names in ALIASES.items():
        aliases.setdefault(league, {}).update({norm(k): v for k, v in names.items()})
    report = collect_scores(queues, args.as_of, aliases,
                            HistoryArchive(args.cache, args.budget, fetch=paced_download(.75)))
    report["reviewed_score_matches"] = link_reviewed_scores(queues, Path("reports"), args.as_of)
    print(json.dumps({"reviewed_score_matches": {key: {field: len(items) for field, items in value.items()}
                                                     for key, value in report["reviewed_score_matches"].items()}}))
    if args.alternative_bundesliga:
        report["alternative_bundesliga"] = alternative_scores(
            queues, args.as_of, aliases, HistoryArchive(args.cache, 4, fetch=paced_download(.75)),
        )
        alternative = report["alternative_bundesliga"]
        print(json.dumps({"alternative_bundesliga": {"sources": len(alternative["source_references"]),
                          "errors": alternative["errors"], "queues": {
                              key: {field: len(items) for field, items in value.items()}
                              for key, value in alternative["queues"].items()}}}))
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({**{k: report[k] for k in ("date_requests", "requests", "cache_hits", "deferred_dates",
                                               "source_failure_counts")},
                      "failed_scoreboard_requests": [{field: e[field] for field in ("url", "category", "retry_deferred")}
                                                     for e in report["errors"]],
                      "queues": {k: {field: len(v) if isinstance(v, list) else v for field, v in queue.items()}
                                 for k, queue in report["queues"].items()}}))


if __name__ == "__main__":
    main()
