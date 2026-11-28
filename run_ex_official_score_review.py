"""Compare reviewed DFL outcomes with the cached EX score queues."""

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from ex_history_archive import atomic_write


def reconcile(official, staged, ledger):
    source = urlsplit(official["source"])
    if source.scheme != "https" or source.netloc != "www.bundesliga.com" or official["league"] != "de.1":
        raise ValueError("Unexpected DFL publication")
    reference = {}
    for day, home, away, hg, ag in official["fixtures"]:
        key = day, home, away
        if (key in reference or home == away or date.fromisoformat(day) >= date.fromisoformat(official["reviewed_on"])
                or any(type(score) is not int or not 0 <= score <= 30 for score in (hg, ag))):
            raise ValueError("Duplicate or malformed official result")
        reference[key] = (hg, ag)

    def index(rows):
        return {(row["date"], row["home"], row["away"]): (row["home_goals"], row["away_goals"])
                for row in rows if row["league"] == "de.1" and row["season"] == official["season"]}

    feeds = {"Football-Data staged": index(staged),
             "ESPN": index(ledger["queues"]["newer"]["provisional_matches"]),
             "OpenLigaDB": index(ledger.get("alternative_bundesliga", {}).get("queues", {})
                                 .get("newer", {}).get("verified", []))}
    results = []
    for key, score in reference.items():
        checks = {name: "UNMATCHED" if key not in values else ("MATCH" if values[key] == score else "CONFLICT")
                  for name, values in feeds.items()}
        results.append({"date": key[0], "home": key[1], "away": key[2], "official_score": score, "checks": checks})
    return {"source": official["source"], "fixtures": results,
            "matches": {name: sum(row["checks"][name] == "MATCH" for row in results) for name in feeds},
            "conflicts": {name: sum(row["checks"][name] == "CONFLICT" for row in results) for name in feeds},
            "scope": "OFFICIAL_MATCH_RESULT_ONLY", "provider_lineage_certified": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    official = json.loads(Path("research/ucl/dfl-score-review.json").read_text())
    result = reconcile(official, json.loads(args.staged.read_text()), json.loads(args.ledger.read_text()))
    atomic_write(args.output, (json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps({"fixtures": len(result["fixtures"]), "matches": result["matches"],
                      "conflicts": result["conflicts"]}))


if __name__ == "__main__":
    main()
