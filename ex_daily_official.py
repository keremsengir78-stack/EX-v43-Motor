"""Independently corroborate exact same-day fixtures using league-owned sources."""

import datetime as dt
import json
import re
from pathlib import Path
from collections import defaultdict

from ex_cross_verify import norm
from ex_history_archive import BudgetExhausted, source_error, utc
from run_ex_additional_official_scores import ENGLISH, FPL, SERIE_A, english_scores, italian_scores, MARSEILLE, marseille_scores

from run_ex_dutch_reconcile import KNVB, identity as dutch_identity, parse_knvb
from run_ex_laliga_bulk import LALIGA, extract as laliga_scores

DUTCH = {"nl.1": "https://www.knvb.nl/competities/eredivisie/uitslagen", "nl.2": KNVB}
UEFA_CONFIG = Path(__file__).with_name("config") / "ucl_matchday5_2026_research.json"
OFFICIAL_LEAGUES = ("en.1", "it.1", "es.1", "nl.1", "nl.2", "fr.1", "UCL")


def uefa_scores(raw, url, stamp):
    from run_ucl_research import uefa_match_entries

    output = []
    headings = {int(n) for n in re.findall(rb"<h2>\s*Matchday (\d+)\s*</h2>", raw)}
    if not headings:
        raise ValueError("No UEFA matchday sections")
    for number in sorted(headings):
        for when, text, _ in uefa_match_entries(raw, number):
            match = re.fullmatch(r"(.+?) (\d{1,2})-(\d{1,2}) (.+)", text)
            if not match or when.date() >= stamp.date():
                continue
            home, hg, ag, away = match.groups()
            if max(int(hg), int(ag)) <= 30:
                output.append({"date": when.date().isoformat(), "home": home, "away": away,
                               "official_score": [int(hg), int(ag)], "source": url,
                               "source_match_id": f"{when:%Y%m%d}:{norm(home)}:{norm(away)}"})
    return output


def archive_candidates(league, archive):
    """Use published full-time results from competition and federation sources."""
    ttl = dt.timedelta(hours=6)
    if league in DUTCH:
        url = DUTCH[league]
        def parse(raw, stamp):
            fixtures = parse_knvb(raw.decode(), stamp.date())
            return [{"date": day, "home": home, "away": away, "official_score": list(score),
                     "source": url, "source_match_id": f"{day}:{home}:{away}"}
                    for (day, home, away), score in fixtures.items()]
        candidates, source = archive.get(url, parse, max_age=ttl)
        return candidates, [source]
    if league == "fr.1":
        candidates, source = archive.get(MARSEILLE, lambda raw, stamp: marseille_scores(raw.decode(), stamp.isoformat()),
                                         max_age=ttl)
        return candidates, [source]
    if league == "UCL":
        url = json.loads(UEFA_CONFIG.read_text())["source"]
        candidates, source = archive.get(url, lambda raw, stamp: uefa_scores(raw, url, stamp), max_age=ttl)
        return candidates, [source]
    if league == "es.1":
        def discover(raw, stamp):
            prefix = "/en-GB/laliga-easports/results/"
            year = stamp.year - (stamp.month < 7)
            season = f"{year}-{(year+1)%100:02d}"
            links = re.findall(re.escape(prefix + season) + r"/gameweek-(\d+)", raw.decode())
            if not links:
                raise ValueError("No official current-season matchday links")
            return [f"https://www.laliga.com{prefix}{season}/gameweek-{week}"
                    for week in dict.fromkeys(links) if 1 <= int(week) <= 38][:3]
        pages, _ = archive.get(LALIGA, discover, max_age=ttl)
        candidates, evidence = [], []
        for url in pages:
            rows, source = archive.get(url, lambda raw, stamp: laliga_scores(raw.decode(), url, stamp.isoformat())[0],
                                       max_age=ttl)
            candidates.extend(rows)
            evidence.append(source)
        return candidates, evidence
    raise ValueError("No official result adapter")


ALIASES = {norm(name): norm(target) for name, target in
           {"Internazionale": "Inter", "AC Milan": "Milan", "Hellas Verona": "Verona"}.items()}


def key(league, day, home, away):
    if league in DUTCH:
        return (league, *dutch_identity(day, home, away))
    if league == "UCL":
        config = json.loads(UEFA_CONFIG.read_text())
        aliases = {norm(variant): norm(club) for group in config["domestic_team_names"].values()
                   for club, variants in group.items() for variant in [club, *variants]}
        return league, day, aliases.get(norm(home), norm(home)), aliases.get(norm(away), norm(away))
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
    for league in OFFICIAL_LEAGUES:
        if not by_league[league]:
            continue
        url = FPL + "fixtures/" if league == "en.1" else SERIE_A if league == "it.1" else DUTCH.get(league)
        try:
            ttl = dt.timedelta(hours=1)
            if league == "en.1":
                catalog, teams_meta = archive.get(FPL + "bootstrap-static/",
                                                  lambda raw, _: json.loads(raw), max_age=ttl)
                candidates, source = archive.get(
                    url, lambda raw, stamp: english_scores(json.loads(raw), catalog, stamp.isoformat()), max_age=ttl)
                sources = [source, teams_meta]
            elif league == "it.1":
                candidates, source = archive.get(
                    url, lambda raw, stamp: italian_scores(raw.decode(), url, stamp.isoformat()), max_age=ttl)
                sources = [source]
            else:
                candidates, sources = archive_candidates(league, archive)
        except (BudgetExhausted, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
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


def main():
    """Probe approved official sources and retain raw evidence on a bounded run."""
    import argparse
    import concurrent.futures
    from urllib.parse import urlsplit

    from ex_history_archive import HistoryArchive, atomic_write, download

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    discovery = {
        "tr.1": "https://www.tff.org/default.aspx?pageID=198",
        "de.1": "https://www.bundesliga.com/en/bundesliga/matchday/2025-2026/34",
        "de.2": "https://www.bundesliga.com/en/2bundesliga/matchday/2025-2026/34",
        "pt.1": "https://www.ligaportugal.pt/competicao/1/classificacao",
        "be.1": "https://www.proleague.be/jpl/kalender",
        "no.1": "https://www.eliteserien.no/resultater",
    }

    def probe(league):
        archive = HistoryArchive(args.output / league, 5)
        try:
            if league == "es.1":
                url = f"{LALIGA}/2026-27/gameweek-6"
                rows, source = archive.get(url, lambda raw, stamp: laliga_scores(raw.decode(), url, stamp.isoformat())[0])
                evidence = [source]
            elif league in discovery:
                url = discovery[league]
                if urlsplit(url).hostname == "www.bundesliga.com" and league == "de.1":
                    from run_ex_dfl_bulk import extract
                    rows, source = archive.get(url, lambda raw, stamp: extract(raw.decode(), url, stamp.isoformat())[0])
                else:
                    raw = download(url)
                    stamp = archive.clock()
                    source = archive.import_capture(url, raw, stamp, archive.digest(raw))
                    rows = []
                evidence = [source]
            else:
                rows, evidence = archive_candidates(league, archive)
            return league, {"parsed_completed_rows": len(rows), "sources": evidence,
                            "state": "MATCH_ROWS_PARSED" if rows else "NO_RESULT_PARSER_OR_ROWS"}
        except (OSError, KeyError, ValueError, TypeError, AttributeError, BudgetExhausted) as exc:
            return league, {"parsed_completed_rows": 0, **source_error("official_source_probe", discovery.get(league), exc)}

    leagues = [*discovery, *(league for league in OFFICIAL_LEAGUES if league not in {"en.1", "it.1"})]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        report = dict(pool.map(probe, leagues))
    atomic_write(args.output / "report.json", json.dumps(report, indent=2).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
