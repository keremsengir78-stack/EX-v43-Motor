"""Isolated UCL research ingestion; never publishes EX FINAL."""
import datetime as dt
import hashlib
import json
import re
import time
import urllib.request
from html import unescape
from urllib.error import HTTPError
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from ex_espn_provider import fetch_espn_scoreboard
from ex_cross_verify import norm
from run_ucl_baselines import FIXTURE_CONFIG
from ex_ucl_strength import audit_league_margins

DAYS=["2026-09-08","2026-09-09","2026-09-10","2026-10-13","2026-10-14","2026-10-20","2026-10-21","2026-11-03","2026-11-04"]
def retry_research_request(request, *args, **kwargs):
    for attempt in range(4):
        try:
            return request(*args, **kwargs)
        except HTTPError as exc:
            if attempt == 3 or exc.code not in {403, 429, 500, 502, 503, 504}:
                raise
            time.sleep(.25 * (2 ** attempt))


def capture_fixture_source(out, label, url):
    with urllib.request.urlopen(url, timeout=15) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Fixture response exceeds size limit")
    filename = f"{label}.raw"
    (out / filename).write_bytes(raw)
    return raw, {
        "url": url, "file": filename, "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


UEFA_BY_TEAM = (
    "https://www.uefa.com/uefachampionsleague/news/"
    "02a8-2176fa83582b-d99f0b27f405-1000--champions-league-league-phase-fixtures-and-results-by-team/"
)
MATCHDAY_DATES = (
    {"2026-09-08", "2026-09-09", "2026-09-10"},
    {"2026-10-13", "2026-10-14"},
    {"2026-10-20", "2026-10-21"},
    {"2026-11-03", "2026-11-04"},
    {"2026-11-24", "2026-11-25"},
)
UEFA_SNAPSHOT = Path(__file__).resolve().parent / "research/ucl/uefa-matchdays-1-5"


def capture_uefa(out, url):
    try:
        raw, meta = retry_research_request(capture_fixture_source, out, "uefa-fixtures", url)
        return raw, {**meta, "mode": "live"}
    except HTTPError as exc:
        if exc.code != 403:
            raise
        live_status = exc.code
    try:
        raw, meta = retry_research_request(capture_fixture_source, out, "uefa-by-team", UEFA_BY_TEAM)
        return raw, {**meta, "mode": "live_by_team", "primary_url": url, "primary_http_status": live_status}
    except HTTPError as exc:
        if exc.code != 403:
            raise
    meta = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())
    raw = UEFA_SNAPSHOT.with_suffix(".html").read_bytes()
    if meta["url"] != url or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError("UEFA snapshot URL or SHA-256 mismatch")
    filename = "uefa-fixtures-replay.raw"
    (out / filename).write_bytes(raw)
    return raw, {**meta, "file": filename, "mode": "archived_excerpt", "live_http_status": live_status}


def uefa_match_entries(raw, matchday):
    html = raw.decode("utf-8")
    if b"fixtures-and-results-by-team/" in raw and "<pk-accordion-item" in html:
        anchors = (r'(\d{2}/\d{2}/\d{4})\s*<a href="[^"]*/uefachampionsleague/match/(\d+)--[^"]+"'
                   r'[^>]*>([^<]+)</a>\s*(?:\((\d{2}:\d{2})\))?')
        entries = {}
        for day, match_id, name, clock in re.findall(anchors, html):
            when = dt.datetime.strptime(day, "%d/%m/%Y")
            if when.date().isoformat() not in MATCHDAY_DATES[matchday - 1]:
                continue
            entry = when, " ".join(unescape(name).split()), clock
            if match_id in entries and entries[match_id] != entry:
                raise ValueError(f"Conflicting UEFA team listings for {match_id}")
            entries[match_id] = entry
        yield from entries.values()
        return
    heading = re.search(rf"<h2>\s*Matchday {matchday}\s*</h2>", html)
    if heading is None:
        raise ValueError(f"UEFA matchday {matchday} heading missing")
    text = re.split(r"<h2\b", html[heading.end():], maxsplit=1)[0]
    days = re.split(r"<b>\w+ (\d+ [A-Za-z]+ \d{4})</b>", text)
    for day, section in zip(days[1::2], days[2::2]):
        when = dt.datetime.strptime(day, "%d %B %Y")
        anchors = r'uefachampionsleague/match/[^"]+"[^>]*>([^<]+)</a>\s*(?:\((\d{2}:\d{2})\))?'
        for name, clock in re.findall(anchors, section):
            yield when, " ".join(unescape(name).split()), clock


def uefa_fixtures(raw, matchday):
    if b"Kick-offs are 21:00 unless stated; all times CET." not in raw:
        raise ValueError("UEFA kickoff convention missing")
    fixtures = []
    for when, name, clock in uefa_match_entries(raw, matchday):
        home, away = name.split(" vs ")
        kickoff = when.replace(
            hour=int((clock or "21:00")[:2]), minute=int((clock or "21:00")[3:]),
            tzinfo=dt.timezone(dt.timedelta(hours=1)),
        )
        fixtures.append((kickoff.astimezone(dt.timezone.utc), norm(home), norm(away)))
    return fixtures


def verify_historical_scores(raw, espn_rows, aliases, matchday):
    uefa = {}
    for number in range(1, matchday):
        for when, text, _ in uefa_match_entries(raw, number):
            match = re.fullmatch(r"(.+?) (\d{1,2})-(\d{1,2}) (.+)", text)
            if match is None:
                raise ValueError(f"Missing UEFA historical score: {text}")
            home, hg, ag, away = match.groups()
            key = when.date().isoformat(), norm(home), norm(away)
            if key in uefa:
                raise ValueError(f"Duplicate UEFA historical fixture: {key}")
            uefa[key] = int(hg), int(ag)
    espn = {}
    for row in espn_rows:
        key = row["date"], aliases[norm(row["home"])], aliases[norm(row["away"])]
        if key in espn:
            raise ValueError(f"Duplicate ESPN historical fixture: {key}")
        espn[key] = row["home_goals"], row["away_goals"]
    conflicts = sorted(key for key in uefa.keys() & espn.keys() if uefa[key] != espn[key])
    return {
        "uefa_rows": len(uefa), "espn_rows": len(espn),
        "exact_score_agreements": sum(espn.get(key) == score for key, score in uefa.items()),
        "missing_in_espn": sorted(uefa.keys() - espn.keys()),
        "missing_in_uefa": sorted(espn.keys() - uefa.keys()),
        "score_conflicts": [{"fixture": key, "uefa": uefa[key], "espn": espn[key]} for key in conflicts],
    }


def espn_fixtures(raw, aliases):
    fixtures = []
    for event in json.loads(raw)["events"]:
        competition, = event["competitions"]
        competitors = {club["homeAway"]: club["team"]["displayName"] for club in competition["competitors"]}
        kickoff = dt.datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        fixtures.append((kickoff, aliases[norm(competitors["home"])], aliases[norm(competitors["away"])]))
    return fixtures


def verify_fixtures(out, config):
    aliases = {}
    for clubs in config["domestic_team_names"].values():
        for name, alternatives in clubs.items():
            for variant in [name, *alternatives]:
                key = norm(variant)
                if key in aliases and aliases[key] != norm(name):
                    raise ValueError(f"Ambiguous UCL club alias: {variant}")
                aliases[key] = norm(name)
    expected = [
        (dt.datetime.fromisoformat(f["kickoff_at"].replace("Z", "+00:00")), norm(f["home"]), norm(f["away"]))
        for f in config["fixtures"]
    ]
    sources = []
    raw, meta = capture_uefa(out, config["source"])
    sources.append(meta)
    uefa_raw = raw
    uefa = uefa_fixtures(raw, config["matchday"])
    espn = []
    for day in sorted({f["date"] for f in config["fixtures"]}):
        url = ("https://site.api.espn.com/apis/site/v2/sports/soccer/"
               f"uefa.champions/scoreboard?dates={day.replace('-', '')}")
        raw, meta = retry_research_request(capture_fixture_source, out, f"espn-fixtures-{day}", url)
        sources.append(meta)
        espn.extend(espn_fixtures(raw, aliases))
    complete = len(set(expected)) == 18 and sorted(expected) == sorted(uefa) == sorted(espn)
    report = {
        "status": "FIXTURES_CORROBORATED" if complete else "FIXTURE_SOURCE_MISMATCH",
        "expected": len(expected), "uefa": len(uefa), "espn": len(espn),
        "sources": sources, "ex_final_allowed": False,
    }
    (out / "fixture_verification.json").write_text(json.dumps(report, indent=2))
    if not complete:
        raise ValueError("UCL fixture manifest disagrees with UEFA or ESPN")
    print("UCL_FIXTURE_VERIFICATION", json.dumps(report))
    return uefa_raw, aliases


def main():
    out=Path("ucl_research_output")
    out.mkdir(exist_ok=True)
    config = json.loads(FIXTURE_CONFIG.read_text())
    uefa_raw, aliases = verify_fixtures(out, config)
    def fetch(day):
        try:
            rows,meta=retry_research_request(fetch_espn_scoreboard, "UCL",day,"2026-11-24",evidence_dir=out/"raw")
            return rows,meta,None
        except (OSError,ValueError,KeyError) as exc:
            return [],None,{"date":day,"error":str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(fetch,DAYS))
    rows=[r for group,_,_ in records for r in group]
    counts=Counter(team for r in rows for team in (r["home"],r["away"]))
    team_profiles={}
    for team in sorted(counts):
        games=[r for r in rows if team in (r["home"],r["away"])]
        profile={}
        for label,subset in (("all",games),("home",[r for r in games if r["home"]==team]),("away",[r for r in games if r["away"]==team])):
            scores=[(r["home_goals"],r["away_goals"]) if r["home"]==team else (r["away_goals"],r["home_goals"]) for r in subset]
            profile[label]={"n":len(scores),"gf":sum(g for g,a in scores),"ga":sum(a for g,a in scores),"wins":sum(g>a for g,a in scores),"draws":sum(g==a for g,a in scores),"over25":sum(g+a>=3 for g,a in scores),"btts":sum(g>0 and a>0 for g,a in scores)}
        team_profiles[team]=profile
    (out/"team_profiles.json").write_text(json.dumps(team_profiles,ensure_ascii=False,indent=2),encoding="utf-8")
    errors=[e for _,_,e in records if e]
    score_verification = verify_historical_scores(uefa_raw, rows, aliases, config["matchday"])
    report={"score_verification":score_verification,"rows":rows,"requests":[m for _,m,_ in records if m],"errors":errors,"team_counts":dict(counts),"coverage_complete":len(rows)==72 and len(counts)==36 and all(n==4 for n in counts.values()) and not errors and score_verification["exact_score_agreements"] == 72,"ex_final_allowed":False}
    (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("UCL_RESEARCH",json.dumps({"rows":len(rows),"teams":len(counts),"complete":report["coverage_complete"],"score_agreements":score_verification["exact_score_agreements"],"errors":errors}))
    if not report["coverage_complete"]:
        raise SystemExit(1)
    leagues = {norm(name): league for league, teams in config["domestic_team_names"].items() for name in teams}
    train, holdout = [], []
    for row in rows:
        group = holdout if row["date"] in MATCHDAY_DATES[3] else train
        group.append((leagues[aliases[norm(row["home"])]], leagues[aliases[norm(row["away"])]],
                      row["home_goals"] - row["away_goals"]))
    strength = audit_league_margins(train, holdout)
    strength["training_matchdays"] = [1, 2, 3]
    strength["holdout_matchday"] = 4
    (out / "league_strength.json").write_text(json.dumps(strength, indent=2))
    print("UCL_LEAGUE_STRENGTH", json.dumps(strength))
if __name__=="__main__":
    main()
