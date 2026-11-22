"""Convert quarantined German shadow remainder into strict-score verification batches.

Candidate aliases never count as approval; the strict reconciler must check
original primary results and independently retrieved secondary scores.
"""
import argparse
import json
from pathlib import Path


def build(data):
    if data.get("ex_final_allowed") is not False or data.get("aliases_approved") is not False:
        raise ValueError("unsafe shadow remainder")
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("missing fixtures")
    clean = []
    seen = set()
    for row in fixtures:
        if row.get("league") != "de.1" or row.get("reason") != "not_found":
            raise ValueError("unexpected German remainder fixture")
        fixture = {key: row[key] for key in ("season", "league", "date", "home", "away")}
        key = tuple(fixture.values())
        if key in seen:
            raise ValueError("duplicate German fixture")
        seen.add(key)
        clean.append(fixture)
    return {"ex_final_allowed": False, "batches": [{"fixtures": clean}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--remaining", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = build(json.loads(Path(args.remaining).read_text(encoding="utf-8")))
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
