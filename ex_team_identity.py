"""Reviewed, time-scoped bindings between provider team identities."""

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from ex_cross_verify import norm
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES, CUP_HISTORY_SLUGS, UEFA_CUPS


def index_identities(document):
    rows, aliases = {}, {}
    leagues = APPROVED_LEAGUES.keys() | CUP_HISTORY_SLUGS.keys()
    for row in document["teams"]:
        club = row["espn_id"]
        evidence = document["evidence"][row["evidence"]]
        alias = norm(row["uefa_name"])
        url = urlsplit(evidence["source"])
        if (club in rows or not club.isdecimal() or not alias or not norm(row["espn_name"])
                or len(row["country"]) != 2 or not row["country"].isalpha()
                or url.scheme != "https" or not url.hostname):
            raise ValueError("Invalid or duplicate team identity")
        if aliases.setdefault(alias, club) != club:
            raise ValueError("Ambiguous UEFA team alias")
        memberships = {}
        for item in row["domestic"]:
            season, league = item["season"], item["league"]
            if (type(season) is not int or league not in leagues - UEFA_CUPS
                    or season in memberships):
                raise ValueError("Invalid or conflicting domestic membership")
            memberships[season] = league
        rows[club] = {**row, "uefa_alias": alias, "memberships": memberships,
                      "review": evidence["source"], "observed": utc(evidence["observed_at"])}
    return rows


@lru_cache(maxsize=1)
def team_identities():
    path = Path(__file__).with_name("config") / "ex_team_identities.json"
    return index_identities(json.loads(path.read_text()))
