"""Independently corroborate exact same-day fixtures using league-owned sources."""

import datetime as dt
import json
from collections import defaultdict

from ex_cross_verify import norm
from ex_history_archive import source_error, utc
from run_ex_additional_official_scores import ENGLISH, FPL, SERIE_A, english_scores, italian_scores

ALIASES = {norm(name): norm(target) for name, target in
           {"Internazionale": "Inter", "AC Milan": "Milan", "Hellas Verona": "Verona"}.items()}


def key(league, day, home, away):
    def name(value):
        value = ENGLISH.get(value, value) if league == "en.1" else value
        normalized = norm(value)
        return ALIASES.get(normalized, normalized) if league == "it.1" else normalized

    return league, day, name(home), name(away)


def league_reviews(forecasts, archive):
    by_league = defaultdict(list)
    for row in forecasts:
        if utc(row["kickoff"]) + dt.timedelta(minutes=90) <= archive.clock():
            by_league[row["league"]].append(row)
    reviews, errors = [], []
    for league in ("en.1", "it.1"):
        if not by_league[league]:
            continue
        url = FPL + "fixtures/" if league == "en.1" else SERIE_A
        try:
            ttl = dt.timedelta(hours=1)
            if league == "en.1":
                catalog, teams_meta = archive.get(FPL + "bootstrap-static/",
                                                  lambda raw, _: json.loads(raw), max_age=ttl)
                candidates, source = archive.get(
                    url, lambda raw, stamp: english_scores(json.loads(raw), catalog, stamp.isoformat()), max_age=ttl)
                sources = [source, teams_meta]
            else:
                candidates, source = archive.get(
                    url, lambda raw, stamp: italian_scores(raw.decode(), url, stamp.isoformat()), max_age=ttl)
                sources = [source]
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append({"league": league, **source_error("official_settlement", url, exc)})
            continue
        identities = defaultdict(list)
        for row in candidates:
            identities[key(league, row["date"], row["home"], row["away"])].append(row)
        for row in by_league[league]:
            day = utc(row["kickoff"]).date().isoformat()
            home, away = row["names"]["home"], row["names"]["away"]
            matches = identities[key(league, day, home, away)]
            if len(matches) != 1:
                continue
            match = matches[0]
            reviews.append({"league": league, "date": day, "home": home, "away": away,
                            "score": match["official_score"], "source": match["source"],
                            "scope": "REVIEWED_OFFICIAL_RESULT", "source_match_id": match["source_match_id"],
                            "verified_at": max(entry["retrieved_at"] for entry in sources), "evidence": sources})
    return reviews, errors
