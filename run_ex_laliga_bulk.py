"""Collect official LALIGA full-time scores with auditable matchday snapshots."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from ex_history_archive import atomic_write
from run_ex_official_sources import capture, read_evidence
from run_ex_source_audit import audit

LALIGA = "https://www.laliga.com/en-GB/laliga-easports/results"
TEAMS = {
    "athletic-club": "Ath Bilbao", "atletico-de-madrid": "Ath Madrid", "fc-barcelona": "Barcelona",
    "celta": "Celta", "deportivo-alaves": "Alaves", "d-alaves": "Alaves", "elche-cf": "Elche",
    "elche-c-f": "Elche", "c-a-osasuna": "Osasuna", "malaga-cf": "Malaga", "r-racing-club": "Santander",
    "getafe-cf": "Getafe", "girona-fc": "Girona", "levante-ud": "Levante", "rayo-vallecano": "Vallecano",
    "rc-celta": "Celta", "rc-deportivo": "La Coruna", "rcd-espanyol": "Espanol",
    "rcd-mallorca": "Mallorca", "real-betis": "Betis", "real-madrid": "Real Madrid",
    "real-oviedo": "Oviedo", "real-sociedad": "Sociedad", "real-valladolid": "Valladolid",
    "real-zaragoza": "Zaragoza", "sevilla-fc": "Sevilla", "ca-osasuna": "Osasuna",
    "ud-las-palmas": "Las Palmas", "valencia-cf": "Valencia", "villarreal-cf": "Villarreal",
}


def extract(page, source, captured_at):
    token = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not token:
        raise ValueError("LALIGA page has no published fixture dataset")
    url = urlsplit(source)
    season, week = url.path.split("/")[-2:]
    props = json.loads(token[1])["props"]["pageProps"]
    if (props["competition"] != "primera-division" or not props["isGameweekPage"]
            or props["gameweek"]["week"] != int(week.removeprefix("gameweek-"))
            or season not in str(props["canonical"])):
        raise ValueError("LALIGA source did not identify the requested season and matchday")
    captured = datetime.fromisoformat(captured_at)
    results, skipped, seen = [], set(), set()
    for match in props["matches"]:
        if match["status"] != "FullTime":
            continue
        kickoff = datetime.fromisoformat(match["date"])
        if kickoff >= captured or match["id"] in seen:
            raise ValueError("Premature or duplicate LALIGA result")
        seen.add(match["id"])
        scores = [match[f"{side}_score"] for side in ("home", "away")]
        if any(type(score) is not int or not 0 <= score <= 30 for score in scores):
            raise ValueError("Invalid LALIGA full-time score")
        slugs = [match[f"{side}_team"]["slug"] for side in ("home", "away")]
        if any(slug not in TEAMS for slug in slugs):
            skipped.update(slug for slug in slugs if slug not in TEAMS)
            continue
        home, away = map(TEAMS.__getitem__, slugs)
        results.append({"league": "es.1", "date": kickoff.date().isoformat(), "home": home, "away": away,
                        "kickoff_at": kickoff.astimezone(timezone.utc).isoformat(), "official_score": scores, "source_match_id": match["id"], "source": source,
                        "proof": "laliga_official_result"})
    return results, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--dfl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = {f"laliga-{season}-{week}": f"{LALIGA}/{season}/gameweek-{week}"
               for season, weeks in (("2025-26", 38), ("2026-27", 13)) for week in range(1, weeks + 1)}
    root = args.output / "raw"
    manifest_path = root / "manifest.json"
    entries = json.loads(manifest_path.read_text()) if manifest_path.exists() else capture(sources, root)
    results, unknown_teams, errors = [], set(), {}
    for label, source in sources.items():
        try:
            entry = entries[label]
            if entry["url"] != source or entry.get("final_url") != source:
                raise ValueError(entry.get("error", "Unexpected LALIGA URL"))
            matches, missing = extract(read_evidence(root, entry), source, entry["captured_at"])
            results.extend(matches)
            unknown_teams.update(missing)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors[label] = str(exc)
    dfl = json.loads(args.dfl.read_text())["matches"] if args.dfl else []
    report = audit(json.loads(args.ledger.read_text()), {"fixtures": [*dfl, *results]})
    stats = {"parsed": len(results), "unknown_teams": sorted(unknown_teams), "errors": errors,
             "audit": report["counts"], "league_season_counts": report["league_season_counts"]}
    for name, data in (("audit", report), ("results", {"matches": results, **stats})):
        atomic_write(args.output / f"{name}.json", (json.dumps(data, indent=2) + "\n").encode())
    print(json.dumps(stats))
    if not any((row["date"], row["home"], row["away"], row["official_score"]) ==
               ("2026-09-06", "Valencia", "Barcelona", [0, 5]) for row in results):
        raise ValueError("Official LALIGA parse failed the reviewed Valencia–Barcelona cross-check")


if __name__ == "__main__":
    main()
