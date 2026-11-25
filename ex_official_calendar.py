"""Read observed fixture identity from approved league and club calendars."""

import datetime as dt
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from ex_official_report_html import plain

ZONES = {"sk.1": "Europe/Bratislava", "ua.1": "Europe/Kyiv", "az.1": "Asia/Baku"}


def fields(pattern, text):
    return [plain(item) for item in re.findall(pattern, text, re.S)]


def slovak_fixtures(html):
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.S):
        names = fields(r'class="schedule_table__team__name">(.*?)</span>', row)
        if len(names) != 2:
            continue
        keys = re.findall(r'class="schedule_table__team__name"><a href="/zapasy/\d+/(\d+)-', row)
        dates = re.findall(r'schedule_table__date--full">[^<]*?(\d{2}\.\d{2}\.\d{4})', row)
        times = fields(r'class="schedule_table__time">(.*?)</td>', row)
        links = set(re.findall(r'href="(/zapas/(\d+)-[a-z0-9-]+)"', row))
        if len(keys) == 2 and len(dates) == len(times) == len(links) == 1:
            link, match_id = links.pop()
            yield match_id, dates[0], times[0], names, keys, link, True


def ukrainian_fixtures(html):
    markers = re.split(r'(?=<div class="tour-(?:date|match)">)', html)
    day = None
    for item in markers:
        if item.startswith('<div class="tour-date">'):
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})</div>', item)
            day = match[1] if match else None
        elif day and fields(r'class="match-tournament">(.*?)</div>', item) == ["UPL"]:
            names = fields(r'class="team (?:first|second)-team">\s*<div class="logo">.*?</div>(.*?)</div>', item)
            links = re.findall(r'<a href="(/en/report/view/(\d+))"[^>]*>\s*([^<]+?)\s*</a>', item)
            if len(names) == 2 and len(links) == 1:
                link, match_id, marker = links[0]
                kickoff = marker if re.fullmatch(r"\d{2}:\d{2}", marker) else None
                yield match_id, day, kickoff, names, [None, None], link, True


def sabah_fixtures(html):
    for card in html.split('<div class="match-card card">')[1:]:
        time = re.search(r'<span>(\d{4}-\d{2}-\d{2})</span>\s*<br\s*/?>\s*<span>(\d{2}:\d{2}),', card)
        sides = fields(r'class="match-info">\s*<span>(.*?)</span>', card)
        state = fields(r'class="match-result">\s*<div class="_content">\s*<span>(.*?)</span>', card)
        if not time or len(sides) != 1 or state != ["--/--"]:
            continue
        names = sides[0].split(" vs ")
        if len(names) == 2 and "Sabah" in names:
            yield None, time[1], time[2], names, [None, None], None, False


PARSERS = {"sk.1": slovak_fixtures, "ua.1": ukrainian_fixtures, "az.1": sabah_fixtures}


def calendar_fixtures(league, html, evidence, day):
    """Produce preliminary match context. An official ID belongs to its source namespace."""
    observed = dt.datetime.fromisoformat(evidence["captured_at"])
    if observed.utcoffset() is None:
        raise ValueError("Calendar capture needs a timezone")
    sources = {}
    for match_id, date, time, names, ids, match_path, competition_verified in PARSERS[league](html):
        try:
            format_ = "%Y-%m-%d" if "-" in date else "%d.%m.%Y"
            kickoff = dt.datetime.strptime(f"{date} {time}", f"{format_} %H:%M")
        except ValueError:
            continue
        if names[0] == names[1] or not all(names):
            continue
        kickoff = kickoff.replace(tzinfo=ZoneInfo(ZONES[league])).astimezone(dt.timezone.utc)
        if kickoff.date() != day or not observed < kickoff:
            continue
        identity = match_id or (kickoff.isoformat(), *names)
        fixture = {"source_match_id": match_id, "source_namespace": f"official:{league}",
                   "kickoff_at": kickoff.isoformat(), "competition_verified": competition_verified,
                   "league": league if competition_verified else None,
                   "names": dict(zip(("home", "away"), names, strict=True)),
                   "source_team_ids": dict(zip(("home", "away"), ids, strict=True)),
                   "official_match_url": urljoin(evidence["final_url"], match_path) if match_path else None,
                   "source": evidence, "espn_event_id": None, "lineup_evidence": None, "odds_evidence": None}
        if identity in sources and sources[identity] != fixture:
            raise ValueError("Conflicting identity in official calendar")
        sources[identity] = fixture
    return list(sources.values())
