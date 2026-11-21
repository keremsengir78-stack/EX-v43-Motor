#!/usr/bin/env python3
"""EX v4.3 data ingestion with integrity checks."""

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


LEAGUES = {
    "en.1": "England Premier League",
    "en.2": "England Championship",
    "de.1": "Germany Bundesliga",
    "de.2": "Germany Bundesliga 2",
    "es.1": "Spain La Liga",
    "it.1": "Italy Serie A",
    "fr.1": "France Ligue 1",
    "nl.1": "Netherlands Eredivisie",
    "pt.1": "Portugal Primeira Liga",
    "be.1": "Belgium First Division",
}

FIELDS = [
    "date", "league", "home", "away",
    "home_goals", "away_goals", "source", "season"
]


def canonical(value):
    value = value.casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", value)


def aliases(path):
    if not path:
        return {}

    data = json.loads(
        Path(path).read_text(encoding="utf-8")
    )
    result = {}

    for league, mapping in data.items():
        result[league] = {}
        for target, names in mapping.items():
            for alias in [target, *names]:
                result[league][canonical(alias)] = target

    return result


def team(value, league, alias):
    return alias.get(league, {}).get(
        canonical(value), value.strip()
    )


def read_openfootball(blob, league, season, alias):
    data = json.loads(blob)

    if not isinstance(data, dict):
        raise ValueError("invalid OpenFootball JSON")

    matches = data.get("matches")
    if not isinstance(matches, list):
        raise ValueError("invalid matches list")

    out = []
    errors = []
    fixtures = 0

    for i, match in enumerate(matches):
        try:
            if not isinstance(match, dict):
                raise ValueError("invalid match object")

            day = dt.date.fromisoformat(
                match["date"][:10]
            )
            home = team(match["team1"], league, alias)
            away = team(match["team2"], league, alias)

            if (
                not home
                or not away
                or canonical(home) == canonical(away)
            ):
                raise ValueError("invalid teams")

            score = match.get("score")

            if score is None:
                fixtures += 1
                continue

            if isinstance(score, list):
                ft = score
            elif isinstance(score, dict):
                ft = score.get("ft")
            else:
                raise ValueError("invalid score format")

            if ft is None:
                fixtures += 1
                continue

            if (
                not isinstance(ft, list)
                or len(ft) != 2
                or any(
                    not isinstance(x, int)
                    or isinstance(x, bool)
                    or x < 0
                    or x > 30
                    for x in ft
                )
            ):
                raise ValueError("invalid full-time score")

            out.append({
                "date": day.isoformat(),
                "league": league,
                "home": home,
                "away": away,
                "home_goals": ft[0],
                "away_goals": ft[1],
                "source": "OpenFootball",
                "season": season,
            })

        except (KeyError, TypeError, ValueError) as exc:
            errors.append({
                "index": i,
                "error": str(exc),
            })

    return out, errors, fixtures


def fetch(url, retries=3, timeout=15):
    allowed = (
        "https://raw.githubusercontent.com/"
        "openfootball/football.json/"
    )

    if not url.startswith(allowed):
        raise ValueError("unapproved URL")

    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "EX-v4.3-data-integrity/1.0"
                },
            )

            with urllib.request.urlopen(
                request, timeout=timeout
            ) as response:
                return response.read()

        except (OSError, urllib.error.URLError):
            if attempt == retries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def run(
    seasons,
    leagues,
    outdir,
    as_of,
    alias_file=None,
    offline=None,
    max_age_days=4,
):
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)

    alias = aliases(alias_file)
    reports = []
    keyed = {}
    conflicts = []
    rejected = []

    cutoff = dt.date.fromisoformat(as_of)

    for season in seasons:
        for league in leagues:
            if league not in LEAGUES:
                raise ValueError(
                    "unknown league " + league
                )

            url = (
                "https://raw.githubusercontent.com/"
                "openfootball/football.json/master/"
                f"{season}/{league}.json"
            )

            local = (
                Path(offline) / season / (league + ".json")
                if offline else None
            )

            try:
                raw = (
                    local.read_bytes()
                    if local else fetch(url)
                )

                digest = hashlib.sha256(
                    raw
                ).hexdigest()

                data, errors, fixtures = read_openfootball(
                    raw, league, season, alias
                )

                for error in errors:
                    rejected.append({
                        "season": season,
                        "league": league,
                        **error,
                    })

                past = [
                    row for row in data
                    if row["date"] < as_of
                ]

                future_removed = len(data) - len(past)

                last = max(
                    (row["date"] for row in past),
                    default=None,
                )

                stale = (
                    not last
                    or (
                        cutoff - dt.date.fromisoformat(last)
                    ).days > max_age_days
                )

                reports.append({
                    "season": season,
                    "league": league,
                    "url": url,
                    "sha256": digest,
                    "rows_before_cutoff": len(past),
                    "future_excluded": future_removed,
                    "fixtures_without_score": fixtures,
                    "last_result": last,
                    "stale": stale,
                    "errors": len(errors),
                    "retrieval": (
                        "local_fixture"
                        if local else "https"
                    ),
                })

                for row in past:
                    key = (
                        row["league"],
                        row["date"],
                        canonical(row["home"]),
                        canonical(row["away"]),
                    )

                    if key in keyed:
                        old = keyed[key]

                        old_score = (
                            old["home_goals"],
                            old["away_goals"],
                        )
                        new_score = (
                            row["home_goals"],
                            row["away_goals"],
                        )

                        if old_score != new_score:
                            conflicts.append({
                                "key": key,
                                "a": old,
                                "b": row,
                            })
                    else:
                        keyed[key] = row

            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                reports.append({
                    "season": season,
                    "league": league,
                    "url": url,
                    "error": str(exc),
                    "stale": True,
                })

    rows = sorted(
        keyed.values(),
        key=lambda row: (
            row["date"],
            row["league"],
            row["home"],
        ),
    )

    with (root / "results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=FIELDS
        )
        writer.writeheader()
        writer.writerows(rows)

    blocked = bool(
        conflicts
        or rejected
        or any(
            report.get("stale")
            for report in reports
        )
    )

    status = (
        "BLOCKED"
        if blocked
        else "INGESTED_SINGLE_PROVIDER_NOT_CROSS_VERIFIED"
    )

    report = {
        "status": status,
        "as_of_exclusive": as_of,
        "total_results": len(rows),
        "sources": reports,
        "conflicts": conflicts,
        "rejected_rows": rejected,
        "independent_sources_confirmed": 0,
        "ex_final_allowed": False,
        "warning": (
            "Single provider. Fixture coverage and "
            "independent source verification required "
            "before EX FINAL."
        ),
    }

    (root / "audit.json").write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return report


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seasons", nargs="+", required=True
    )
    parser.add_argument(
        "--leagues", nargs="+", required=True
    )
    parser.add_argument(
        "--as-of", required=True
    )
    parser.add_argument(
        "--outdir", default="ex_data"
    )
    parser.add_argument("--aliases")
    parser.add_argument("--offline")
    parser.add_argument(
        "--max-age-days", type=int, default=4
    )

    args = parser.parse_args()

    report = run(
        args.seasons,
        args.leagues,
        args.outdir,
        args.as_of,
        args.aliases,
        args.offline,
        args.max_age_days,
    )

    print(json.dumps({
        "status": report["status"],
        "rows": report["total_results"],
        "report": str(
            Path(args.outdir) / "audit.json"
        ),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
