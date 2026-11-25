"""Discover Azerbaijani top-flight matches and their published PFL protocol PDFs."""

import argparse
import datetime as dt
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from ex_history_archive import atomic_write, utc
from ex_pfl_protocol import extract_minutes, pdf_layout
from run_ex_official_sources import capture, read_bytes

PFL = "https://pfl.az/api/v1"
PFL_SEASONS = f"{PFL}/seasons?project_id=1"
MONTHS = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avqust",
          "sentyabr", "oktyabr", "noyabr", "dekabr")


def official_json(root, label, url):
    evidence = capture({label: url}, root)[label]
    if evidence.get("final_url") != url:
        raise ValueError(evidence.get("error", "Unexpected PFL response URL"))
    return json.loads(read_bytes(root, evidence)), evidence


def positive_id(value):
    if type(value) is not int or value < 1:
        raise ValueError("Invalid PFL identity")
    return value


def league_ids(payload, years):
    for season in payload["data"]:
        if season["title"] not in years:
            continue
        for league in season["leagues"]:
            if league["project"]["id"] == 1 and league["is_elimination"] == 0:
                yield season["title"], positive_id(league["id"])


def match_plan(payload, league_id, evidence):
    for tour in payload["data"]:
        if tour["league"]["id"] != league_id:
            raise ValueError("PFL tour league does not match the requested competition")
        for game in tour["games"]:
            kickoff = dt.datetime.strptime(game["start_date"], "%d/%m/%Y %H:%M").replace(
                tzinfo=ZoneInfo("Asia/Baku"))
            clubs = [game[f"club_{side}"] for side in (1, 2)]
            ids = [positive_id(club["id"]) for club in clubs]
            names = [club["title"] for club in clubs]
            if ids[0] == ids[1] or not all(names):
                raise ValueError("Invalid PFL home and away identity")
            pdf = game.get("protocol_src")
            if pdf and (urlsplit(pdf).scheme != "https" or urlsplit(pdf).netloc not in {"pfl.az", "www.pfl.az"}
                        or not re.fullmatch(r"/storage/games/files/[a-f0-9]+_\d+\.pdf", urlsplit(pdf).path)
                        or urlsplit(pdf).query or urlsplit(pdf).fragment):
                raise ValueError("PFL did not publish a supported protocol URL")
            yield {"official_match_id": positive_id(game["id"]), "official_league_id": league_id,
                   "kickoff_at": kickoff.astimezone(dt.timezone.utc).isoformat(),
                   "date_label": f"{kickoff.day} {MONTHS[kickoff.month - 1]} {kickoff.year}",
                   "source_team_ids": dict(zip(("home", "away"), ids, strict=True)),
                   "names": dict(zip(("home", "away"), names, strict=True)), "status": game["status"],
                   "venue": game.get("stadion"), "protocol_url": pdf, "calendar_evidence": evidence}


def fixtures(root, years):
    payload, _ = official_json(root / "seasons", "pfl-seasons", PFL_SEASONS)
    leagues = list(league_ids(payload, years))
    if sorted(year for year, _ in leagues) != sorted(years):
        raise ValueError("One PFL top-flight competition is required per requested season")
    result = {}
    for year, league_id in leagues:
        page, pages = 1, 1
        while page <= pages:
            query = f"{PFL}/tours/get-games?league_id={league_id}"
            if page > 1:
                query += f"&page={page}"
            payload, evidence = official_json(root / f"league-{league_id}-page-{page}", "pfl-tours", query)
            if payload["current_page"] != page or not page <= payload["last_page"] <= 40:
                raise ValueError("Invalid PFL tour pagination")
            pages = payload["last_page"]
            for game in match_plan(payload, league_id, evidence):
                key = game["official_match_id"]
                row = {**game, "season": year}
                if key in result and result[key] != row:
                    raise ValueError("Conflicting PFL fixture or PDF identity across tours")
                result[key] = row
            page += 1
    pdfs = [game["protocol_url"] for game in result.values() if game["protocol_url"]]
    if len(pdfs) != len(set(pdfs)):
        raise ValueError("One PFL protocol URL is assigned to multiple matches")
    return list(result.values())


def collect(root, years, limit, offset):
    plan = fixtures(root, years)
    candidates = [row for row in plan if row["status"] == 3 and row["protocol_url"]
                  and utc(row["kickoff_at"]) < utc(row["calendar_evidence"]["captured_at"])]
    selected = {f'pfl-{row["official_match_id"]}': row
                for row in sorted(candidates, key=lambda row: row["kickoff_at"], reverse=True)[offset:offset+limit]}
    evidence = capture({key: row["protocol_url"] for key, row in selected.items()}, root / "pdfs", reuse=True)
    matches, rejected = {}, {}
    for label, row in selected.items():
        try:
            meta = evidence[label]
            if meta.get("final_url") != row["protocol_url"]:
                raise ValueError(meta.get("error", "Unexpected PDF redirect"))
            minutes = extract_minutes(pdf_layout(read_bytes(root / "pdfs", meta)),
                                      row["names"]["home"], row["names"]["away"], row["date_label"])
            matches[label] = {**row, "minutes": minutes, "protocol_evidence": meta,
                              "basis": "NOMINAL_REGULATION"}
        except (OSError, KeyError, ValueError) as exc:
            rejected[label] = str(exc)
    atomic_write(root / "fixtures.json", (json.dumps(plan, ensure_ascii=False) + "\n").encode())
    result = {"discovered_fixtures": len(plan), "published_protocols": len(candidates), "processed": len(selected),
              "matches": matches, "rejected": rejected, "ex_final_allowed": False}
    atomic_write(root / "minutes.json", (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    return {**result, "matches": list(matches)}



def context_fixture(game):
    key = game["official_match_id"]
    return {**game, "league": "az.1", "competition_verified": True,
            "source_match_id": str(key), "source_namespace": "official:az.1",
            "official_match_url": f"{PFL}/games/show/{key}?withActions=true",
            "espn_event_id": None, "odds_evidence": None, "lineup_evidence": None,
            "roster_observation": None}


def roster_context(game, data, evidence):
    clubs = [data[f"club_{side}"] for side in (1, 2)]
    at = utc(game["kickoff_at"])
    if (data["id"] != game["official_match_id"] or data["league"]["id"] != game["official_league_id"]
            or data["status"] != 0 or [club["id"] for club in clubs] != list(game["source_team_ids"].values())
            or dt.datetime.strptime(data["start_date"], "%d/%m/%Y %H:%M").replace(
                tzinfo=ZoneInfo("Asia/Baku")) != at or utc(evidence["captured_at"]) >= at):
        raise ValueError("PFL pregame fixture detail identity mismatch")
    roster = {side: len(club.get("players") or []) for side, club in zip(("home", "away"), clubs, strict=True)}
    return {"counts": roster, "source": evidence, "scope": "PUBLISHED_CLUB_SQUADS"}


def prematch(root, day):
    """Archive the published PFL fixture and squad payload during the pregame window."""
    start = day.year if day.month >= 7 else day.year - 1
    result = []
    for game in fixtures(root, [f"{start}-{start + 1}"]):
        at = utc(game["kickoff_at"])
        if (game["status"] != 0 or at.date() != day
                or not utc(game["calendar_evidence"]["captured_at"]) < at):
            continue
        key = game["official_match_id"]
        match = context_fixture(game)
        try:
            payload, evidence = official_json(root / f"detail-{key}", "pfl-match", match["official_match_url"])
            match["roster_observation"] = roster_context(game, payload["data"], evidence)
        except (KeyError, OSError, ValueError, TypeError) as exc:
            match["roster_issue"] = str(exc)
        result.append(match)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--limit", type=int, default=20, choices=range(1, 61))
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--seasons", nargs="+", default=["2025-2026", "2026-2027"])
    args = p.parse_args()
    if args.offset < 0:
        p.error("Offset must be nonnegative")
    result = collect(args.output, args.seasons, args.limit, args.offset)
    print(json.dumps(result, ensure_ascii=False))
    if not result["published_protocols"] or (args.offset == 0 and not result["matches"]):
        raise SystemExit("No verified PFL protocol minutes")


if __name__ == "__main__":
    main()
