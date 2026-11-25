"""Corroborate scores from Lega Serie A and the official Premier League fantasy feed."""

import argparse
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from ex_history_archive import atomic_write, utc
from run_ex_official_sources import capture, read_evidence
from run_ex_source_audit import audit

SERIE_A = "https://en.legaseriea.it/serie-a"
FPL = "https://fantasy.premierleague.com/api/"
ENGLISH = {
    "Arsenal": "Arsenal", "Aston Villa": "Aston Villa", "Bournemouth": "Bournemouth",
    "Brentford": "Brentford", "Brighton": "Brighton", "Burnley": "Burnley", "Chelsea": "Chelsea",
    "Coventry": "Coventry", "Crystal Palace": "Crystal Palace", "Everton": "Everton", "Fulham": "Fulham",
    "Hull": "Hull", "Ipswich": "Ipswich", "Leeds": "Leeds", "Leicester": "Leicester",
    "Liverpool": "Liverpool", "Man City": "Man City", "Man Utd": "Man United", "Newcastle": "Newcastle",
    "Nott'm Forest": "Nott'm Forest", "Southampton": "Southampton", "Spurs": "Tottenham",
    "Sunderland": "Sunderland", "West Ham": "West Ham", "Wolves": "Wolves",
}
SCORES = {"Inter": "Inter", "Milan": "Milan", "Hellas Verona": "Verona"}


def final_score(values):
    if any(type(goal) is not int or not 0 <= goal <= 30 for goal in values):
        raise ValueError("Invalid official final score")
    return values


def italian_scores(html, source, captured_at):
    chunks = [json.loads(row)[1] for row in re.findall(
        r'<script>self\.__next_f\.push\((\[1,\s*".*?"\])\)</script>', html, re.S)]
    body = "".join(chunks)
    decoder = json.JSONDecoder()
    result = {}
    for match in re.finditer(r'\{"providerId":"[^"]+","seasonId":"serie-a::Football_Season::[a-f0-9]+"', body):
        item, _ = decoder.raw_decode(body, match.start())
        if (item.get("status") != "FINISHED" or item.get("phase") != "FULL_TIME"
                or item.get("roundName") != "Campionato"):
            continue
        match_id = item["matchId"].removeprefix("serie-a::Football_Match::")
        if not re.fullmatch(r"[a-f0-9]{32}", match_id):
            raise ValueError("Invalid Lega Serie A fixture ID")
        kickoff = utc(item["matchDateUtc"])
        if kickoff >= utc(captured_at):
            raise ValueError("Lega Serie A postgame status precedes kickoff")
        names = [item[side]["shortName"] for side in ("home", "away")]
        scores = final_score([item["providerHomeScore"], item["providerAwayScore"]])
        if scores != [item["homeScorePush"], item["awayScorePush"]] or names[0] == names[1]:
            raise ValueError("Conflicting Lega Serie A fixture fields")
        path = item["matchUrl"]
        if not re.fullmatch(rf"/serie-a/match/{match_id}/[a-z0-9-]+/?", path):
            raise ValueError("Lega Serie A fixture URL does not match the embedded identity")
        home, away = [SCORES.get(name, name) for name in names]
        candidate = {"league": "it.1", "date": kickoff.date().isoformat(), "home": home, "away": away,
                     "official_score": scores, "source_match_id": match_id, "source": urljoin(source, path),
                     "proof": "lega_serie_a_official_result"}
        if match_id in result and result[match_id] != candidate:
            raise ValueError("Conflicting Lega Serie A result")
        result[match_id] = candidate
    return list(result.values())


def english_scores(games, catalog, captured_at):
    teams = {row["id"]: row["name"] for row in catalog["teams"]}
    if len(teams) != 20:
        raise ValueError("Official Premier League roster does not have 20 identities")
    result = {}
    for game in games:
        if game["finished"] is not True or game["kickoff_time"] is None:
            continue
        kickoff = utc(game["kickoff_time"])
        if kickoff >= utc(captured_at):
            raise ValueError("Official Premier League postgame status precedes kickoff")
        home, away = (ENGLISH[teams[game[f"team_{side}"]]] for side in ("h", "a"))
        match_id = game["id"]
        if match_id in result or home == away:
            raise ValueError("Duplicate or malformed Premier League result")
        result[match_id] = {"league": "en.1", "date": kickoff.date().isoformat(), "home": home, "away": away,
                            "official_score": final_score([game["team_h_score"], game["team_a_score"]]),
                            "source_match_id": match_id, "source": FPL + "fixtures/",
                            "proof": "premier_league_official_fantasy_result"}
    return list(result.values())


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ledger", type=Path, required=True)
    cli.add_argument("--laliga", type=Path, required=True)
    cli.add_argument("--dfl", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    raw = args.output / "raw"
    sources = {"serie-a": SERIE_A, "fpl-fixtures": FPL + "fixtures/", "fpl-teams": FPL + "bootstrap-static/"}
    pages = capture(sources, raw)

    def read(key):
        entry = pages[key]
        if entry.get("final_url") != sources[key]:
            raise ValueError(entry.get("error", "Unexpected official source redirect"))
        return read_evidence(raw, entry)

    rows, errors = {}, {}
    for name, extract in {
        "it.1": lambda: italian_scores(read("serie-a"), SERIE_A, pages["serie-a"]["captured_at"]),
        "en.1": lambda: english_scores(json.loads(read("fpl-fixtures")), json.loads(read("fpl-teams")),
                                      pages["fpl-fixtures"]["captured_at"]),
    }.items():
        try:
            rows[name] = extract()
            if not rows[name]:
                errors[name] = "No supported completed games"
        except (KeyError, OSError, ValueError, TypeError) as exc:
            errors[name] = str(exc)
    previous = [*json.loads(args.laliga.read_text())["matches"], *json.loads(args.dfl.read_text())["matches"]]
    report = audit(json.loads(args.ledger.read_text()), {"fixtures": [*previous, *sum(rows.values(), [])]})
    stats = {"parsed": {league: len(matches) for league, matches in rows.items()}, "errors": errors,
             "audit": report["counts"], "league_season_counts": report["league_season_counts"]}
    for name, data in (("audit", report), ("results", {"matches": sum(rows.values(), []), **stats})):
        atomic_write(args.output / f"{name}.json", (json.dumps(data, indent=2) + "\n").encode())
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
