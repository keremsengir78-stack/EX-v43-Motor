"""Normalize individually reviewed official lineup timelines in bulk."""

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from ex_history_archive import atomic_write
from ex_official_minutes import minutes_from_timeline


OFFICIAL_HOSTS = {"sk.1": {"www.nikeliga.sk", "www.skslovan.com"},
                  "cz.1": {"www.chanceliga.cz"}, "ua.1": {"upl.ua", "www.upl.ua"},
                  "az.1": {"pfl.az", "www.pfl.az"}}


def parse_parenthetical_lineup(text):
    """Parse the official report's team line after its identity was reviewed."""
    if not isinstance(text, str) or "\n" in text or ":" in text:
        raise ValueError("Expected one extracted team lineup line")
    starters, changes = [], []
    for segment in re.split(r",\s*|\s+[–-]\s+", text):
        match = re.fullmatch(r"([^()]+?)(?:\s*\((\d{1,2})\.\s+([^()]+)\))?", segment.strip())
        if not match or not match[1].strip():
            raise ValueError("Unrecognized report lineup token")
        player = match[1].strip()
        starters.append(player)
        if match[2]:
            changes.append((int(match[2]), player, match[3].strip()))
    return starters, sorted(changes, key=lambda row: row[0])


def normalize(rows):
    seen, minutes, errors = set(), [], []
    for row in rows:
        try:
            league = row["league"]
            source = urlsplit(row["source"])
            official_id = row["official_match_id"]
            key = league, official_id
            if (source.scheme != "https" or source.netloc not in OFFICIAL_HOSTS[league]
                    or not isinstance(official_id, str) or not official_id.isascii() or not official_id.isdigit()
                    or row["home"] == row["away"] or key in seen
                    or row.get("scope", "").lower().find("reviewed") < 0):
                raise ValueError("Unreviewable competition, source or fixture identity")
            date.fromisoformat(row["match_date"])
            if set(row["teams"]) != {"home", "away"}:
                raise ValueError("Both match timelines are required")
            seen.add(key)
            teams = {}
            for side, timeline in row["teams"].items():
                if timeline.get("dismissals") or timeline.get("extra_time"):
                    raise ValueError("Nonstandard playing time requires another reviewed representation")
                if "lineup_text" in timeline:
                    if league != "cz.1":
                        raise ValueError("Parenthetical report template is only reviewed for Chance Liga")
                    starters, changes = parse_parenthetical_lineup(timeline["lineup_text"])
                else:
                    starters, changes = timeline["starters"], timeline["substitutions"]
                teams[side] = minutes_from_timeline(starters, changes)
            minutes.append({**{field: row[field] for field in ("league", "official_match_id", "match_date",
                                                               "home", "away", "source")},
                            "minutes": teams, "scope": "REVIEWED_NOMINAL_REGULATION_ONLY"})
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append({"match": row.get("official_match_id") if isinstance(row, dict) else None,
                           "error": str(exc)})
    return {"minutes": minutes, "errors": errors, "leagues": sorted({r["league"] for r in minutes}),
            "league_registry": sorted(OFFICIAL_HOSTS), "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for path in args.input:
        data = json.loads(path.read_text())
        rows.extend(data if isinstance(data, list) else [data])
    result = normalize(rows)
    atomic_write(args.output, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"matches": len(result["minutes"]), "errors": result["errors"],
                      "leagues": result["leagues"]}))


if __name__ == "__main__":
    main()
