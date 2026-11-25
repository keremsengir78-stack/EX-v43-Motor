"""Independently corroborate exact same-day fixtures using league-owned sources."""

import datetime as dt
import json
import re
from pathlib import Path
from collections import defaultdict

from ex_benelux_results import (BELGIUM_CALENDAR, BELGIUM_SAMPLE, PORTUGAL_SAMPLE, belgian_matches,
                                belgian_results, embedded, portuguese_related_links, portuguese_results)
from ex_cross_verify import norm
from ex_history_archive import BudgetExhausted, source_error, utc
from run_ex_additional_official_scores import ENGLISH, FPL, SERIE_A, english_scores, italian_scores, MARSEILLE, marseille_scores

from run_ex_dutch_reconcile import KNVB, identity as dutch_identity, parse_knvb
from run_ex_laliga_bulk import LALIGA, extract as laliga_scores
from run_ex_dfl_bulk import TEAMS as DFL_TEAMS, extract as dfl_scores
from ex_official_report_html import plain

DUTCH = {"nl.1": "https://www.knvb.nl/competities/eredivisie/uitslagen", "nl.2": KNVB}
UEFA_CONFIG = Path(__file__).with_name("config") / "ucl_matchday5_2026_research.json"
GERMANY = {"de.1": ("bl1", "bundesliga"), "de.2": ("bl2", "2bundesliga")}
NORWAY = "https://www.eliteserien.no/resultater"
TURKEY = "https://www.tff.org/default.aspx?pageID=198"
OFFICIAL_LEAGUES = ("en.1", "it.1", "es.1", "nl.1", "nl.2", "fr.1", "UCL", "de.1", "de.2", "no.1", "tr.1", "be.1", "pt.1")


def norway_scores(raw, stamp):
    rows = []
    page = raw.decode()
    if "<title>Resultater / Eliteserien</title>" not in page:
        raise ValueError("Unexpected Norwegian competition page")
    for card in re.findall(r'<tr class="schedule__match schedule__match--played[^"]*".*?</tr>', page, re.S):
        if 'alt="Eliteserien"' not in card:
            continue
        clubs = re.search(r'schedule__match__item--teams">(.*?)</td>', card, re.S)
        score = re.search(r'schedule__match__item--result">(\d{1,2})-(\d{1,2})</td>', card)
        date = re.search(r'--date">(\d{2})\.(\d{2})\.<span[^>]*>(\d{4})</span>', card)
        ref = re.search(r'kamp\?id=(\d+)', card)
        if not all((clubs, score, date, ref)):
            continue
        day = dt.date(int(date[3]), int(date[2]), int(date[1]))
        names = plain(re.sub(r'<span class="schedule__match__score">.*?</span>', '', clubs[1], flags=re.S))
        home, sep, away = names.partition(" - ")
        values = list(map(int, score.groups()))
        if (day < stamp.date() and sep and home and away and max(values) <= 30):
            rows.append({"date": day.isoformat(), "home": home, "away": away, "official_score": values,
                         "source": NORWAY, "source_match_id": ref[1]})
    if not rows:
        raise ValueError("No completed Eliteserien results")
    return rows


def turkey_scores(raw, stamp):
    page = raw.decode("cp1254") if b"windows-1254" in raw.lower() else raw.decode("utf-8")
    if "per Lig Fikst" not in page or "haftaninMaclariTr" not in page:
        raise ValueError("Unexpected TFF competition page")
    rows = []
    for card in re.findall(r'<tr class="haftaninMaclariTr">(.*?)</tr>', page, re.S):
        date = re.search(r'lblTarih">([0-9.]{10})</span>', card)
        goals = [value.strip() for value in re.findall(r'Label[56]">([^<]*)</span>', card)]
        teams = [plain(value) for value in re.findall(r'Label(?:4|1)">([^<]+)</span>', card)]
        key = re.search(r'macId=(\d+)', card)
        if not date or len(teams) != 2 or not key or len(goals) != 2:
            continue
        day = dt.datetime.strptime(date[1], "%d.%m.%Y").date()
        if day >= stamp.date() or any(not goal.isascii() or not goal.isdigit() or int(goal) > 30 for goal in goals):
            continue
        rows.append({"date": day.isoformat(), "home": teams[0], "away": teams[1],
                     "official_score": list(map(int, goals)), "source": TURKEY, "source_match_id": key[1]})
    return rows


def german_scores(league, fixtures, archive):
    code, route = GERMANY[league]
    target = defaultdict(set)
    for row in fixtures:
        target[row["season"]].add(utc(row["kickoff"]).date())
    results, evidence = [], []
    for year, days in sorted(target.items()):
        index = f"https://api.openligadb.de/getmatchdata/{code}/{year}"
        def rounds(raw, _):
            return sorted({item["group"]["groupOrderID"] for item in json.loads(raw)
                           if dt.date.fromisoformat(item["matchDateTimeUTC"][:10]) in days})
        week_numbers, _ = archive.get(index, rounds, max_age=dt.timedelta(hours=24))
        for week in week_numbers:
            if type(week) is not int or not 1 <= week <= 34:
                raise ValueError("Invalid DFL matchday locator")
            url = f"https://www.bundesliga.com/en/{route}/matchday/{year}-{year+1}/{week}"
            matches, source = archive.get(url, lambda raw, stamp: dfl_scores(
                raw.decode(), url, stamp.isoformat(), require_finished=True, allow_named_teams=True)[0],
                max_age=dt.timedelta(hours=24))
            results.extend({**row, "source_match_id": row["source"]} for row in matches)
            evidence.append(source)
    return results, evidence


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


def belgian_links(raw, stamp):
    links = {}
    for item in belgian_matches(embedded(raw, b"__NEXT_DATA__")):
        slug = item["slug"]
        if not re.fullmatch(r"seizoen-[0-9-]+-jupiler-pro-league-[a-z0-9-]+", slug):
            continue
        anchor = (utc(item["time"]), key("be.1", item["date"], item["homeTeam"]["name"], item["awayTeam"]["name"]))
        url = f"https://www.proleague.be/wedstrijden/{slug}"
        if links.setdefault(anchor, url) != url:
            raise ValueError("Ambiguous Belgian official fixture link")
    return links


def belgian_match_hint(links, kickoff, clubs):
    return links.get((kickoff, key("be.1", kickoff.date().isoformat(), clubs["home"], clubs["away"])))


def archive_candidates(league, archive, fixtures=()):
    """Use published full-time results from competition and federation sources."""
    ttl = dt.timedelta(hours=6)
    if league in {"be.1", "pt.1"}:
        days = {utc(row["kickoff"]).date().isoformat() for row in fixtures}
        urls = {}
        if league == "be.1":
            for fixture in fixtures:
                hint = fixture.get("official_match_url")
                if isinstance(hint, str) and re.fullmatch(
                        r"https://www\.proleague\.be/wedstrijden/seizoen-[0-9-]+-jupiler-pro-league-[a-z0-9-]+", hint):
                    urls[hint] = None
            if "2026-11-21" in days:
                urls[BELGIUM_SAMPLE] = None
            def links(raw, _):
                rows = belgian_matches(embedded(raw, b"__NEXT_DATA__"))
                return [f"https://www.proleague.be/wedstrijden/{row['slug']}" for row in rows
                        if row["date"] in days and re.fullmatch(r"[a-z0-9-]+", row["slug"])]
            if days:
                try:
                    more, _ = archive.get(BELGIUM_CALENDAR, links, max_age=ttl)
                    urls.update(dict.fromkeys(more))
                except (OSError, ValueError):
                    if not urls:
                        raise
            parse = belgian_results
        else:
            if days:
                links, _ = archive.get(PORTUGAL_SAMPLE, lambda raw, _: portuguese_related_links(raw, days),
                                       max_age=ttl)
                urls.update(dict.fromkeys(links))
            if "2026-11-08" in days:
                urls[PORTUGAL_SAMPLE] = None
            parse = portuguese_results
        entries, evidence = [], []
        for url in list(urls)[:9]:
            rows, source = archive.get(url, lambda raw, stamp: parse(raw, url, stamp), max_age=ttl)
            entries.extend(rows)
            evidence.append(source)
        return entries, evidence
    if league in GERMANY:
        return german_scores(league, fixtures, archive)
    if league in {"tr.1", "no.1"}:
        url, parse = (TURKEY, turkey_scores) if league == "tr.1" else (NORWAY, norway_scores)
        rows, source = archive.get(url, parse, max_age=ttl)
        return rows, [source]
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
        if league in GERMANY:
            value = DFL_TEAMS.get(value, value)
            german = {"Bayern München": "Bayern Munich", "Borussia Dortmund": "Dortmund",
                      "VfB Stuttgart": "Stuttgart", "Eintracht Frankfurt": "Ein Frankfurt",
                      "Bayer Leverkusen": "Leverkusen", "Borussia Monchengladbach": "M'gladbach"}
            value = german.get(value, value)
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
                candidates, sources = archive_candidates(league, archive, by_league[league])
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
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args()
    discovery = {
        "tr.1": "https://www.tff.org/default.aspx?pageID=198",
        "de.1": "https://www.bundesliga.com/en/bundesliga/matchday/2025-2026/34",
        "de.2": "https://www.bundesliga.com/en/2bundesliga/matchday/2025-2026/34",
        "pt.1": "https://www.ligaportugal.pt/competicao/915/liga-portugal-betclic/20262027/calendario",
        "be.1": "https://www.proleague.be/jpl-kalender?activeTab=results",
        "no.1": "https://www.eliteserien.no/resultater",
    }

    def probe(league):
        archive = HistoryArchive(args.output / league, 5)
        try:
            if league == "es.1":
                url = f"{LALIGA}/2026-27/gameweek-6"
                rows, source = archive.get(url, lambda raw, stamp: laliga_scores(raw.decode(), url, stamp.isoformat())[0])
                evidence = [source]
            elif league in {"be.1", "pt.1"}:
                date = "2026-11-21" if league == "be.1" else "2026-11-08"
                fixtures = [{"kickoff": date + "T20:00:00Z"}]
                if league == "pt.1":
                    fixtures.append({"kickoff": "2026-10-31T20:30:00Z"})
                rows, evidence = archive_candidates(league, archive, fixtures)
            elif league in {"tr.1", "no.1"}:
                rows, evidence = archive_candidates(league, archive)
            elif league in discovery:
                url = discovery[league]
                if urlsplit(url).hostname == "www.bundesliga.com":
                    rows, source = archive.get(url, lambda raw, stamp: dfl_scores(
                        raw.decode(), url, stamp.isoformat(), require_finished=True, allow_named_teams=True)[0])
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

    if args.discover:
        samples = {
            "portugal-team": "https://www.ligaportugal.pt/equipa/157/fc-porto/resultados",
            "portugal-match": "https://www.ligaportugal.pt/match/20262027/ligaportugalbetclic/11/9?tab=match_timeline",
            "belgium-previous": "https://www.proleague.be/jpl-kalender?activeTab=results&gameweekId=44d68a68-8e0e-4ef5-b98d-b540b1bb97d3",
            "belgium-week": "https://www.proleague.be/jpl-kalender?activeTab=results&gameweek=44d68a68-8e0e-4ef5-b98d-b540b1bb97d3",
            "turkey-previous": "https://www.tff.org/default.aspx?pageID=198&hafta=13",
        }
        def capture_sample(item):
            name, url = item
            archive = HistoryArchive(args.output / name, 1)
            try:
                _, evidence = archive.get(url, lambda raw, _: len(raw))
                return name, {"source": evidence}
            except (OSError, ValueError) as exc:
                return name, source_error("official_source_discovery", url, exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            report = dict(pool.map(capture_sample, samples.items()))
        atomic_write(args.output / "report.json", json.dumps(report, indent=2).encode())
        print(json.dumps(report))
        return
    leagues = sorted(set(discovery) | (set(OFFICIAL_LEAGUES) - {"en.1", "it.1"}))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        report = dict(pool.map(probe, leagues))
    atomic_write(args.output / "report.json", json.dumps(report, indent=2).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
