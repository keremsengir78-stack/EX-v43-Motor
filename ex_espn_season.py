"""Collect ESPN season results using its published daily scoreboard calendar."""

import datetime as dt
import json

from ex_espn_provider import ESPN_LEAGUES, parse_espn_scoreboard
from ex_history_archive import utc
from ex_history_sources import ESPN


def daily_url(league, day):
    return f"{ESPN}/{ESPN_LEAGUES[league]}/scoreboard?dates={day:%Y%m%d}"


def checked_board(raw, league):
    data = json.loads(raw)
    rows = data["leagues"]
    if len(rows) != 1 or rows[0]["slug"] != ESPN_LEAGUES[league]:
        raise ValueError("ESPN board competition mismatch")
    return data


def collect_season(archive, league, start, end, cutoff, day_limit=None):
    # An anchor well inside the competition season selects the correct calendar.
    anchor = start + dt.timedelta(days=105)
    url = daily_url(league, anchor)
    board, seed = archive.get(url, lambda raw, _: checked_board(raw, league),
                              max_age=dt.timedelta(hours=24))
    calendar = board["leagues"][0]["calendar"]
    if not calendar:
        raise ValueError("Missing ESPN season calendar")
    if all(isinstance(value, str) for value in calendar):
        dates = {utc(value).date() for value in calendar}
        if not all(start <= date < end for date in dates):
            raise ValueError("ESPN returned the wrong discrete season calendar")
    elif league == "UCL" and len(calendar) == 1:
        bounds = calendar[0]
        if utc(bounds["startDate"]).date() != start or utc(bounds["endDate"]).date() < end - dt.timedelta(days=1):
            raise ValueError("ESPN returned the wrong UEFA season calendar")
        dates = {start + dt.timedelta(days=i) for i in range((min(cutoff, end) - start).days)}
    else:
        raise ValueError("Unsupported ESPN season calendar template")
    days = sorted((day for day in dates if day < cutoff), reverse=True)
    selected = days[:day_limit]
    rows, rejected, sources = [], [], [seed]
    for day in selected:
        url = daily_url(league, day)
        try:
            payload, meta = archive.get(url, lambda raw, _: checked_board(raw, league),
                                        max_age=dt.timedelta(hours=12) if (cutoff-day).days <= 2 else None)
            # UEFA knockout scores can include extra time. Only regulation
            # completions enter the common regulation-goals dataset.
            completed = [event for event in payload["events"] if
                         event.get("status", {}).get("type", {}).get("name") == "STATUS_FULL_TIME"]
            rows.extend(parse_espn_scoreboard({**payload, "events": completed}, league,
                                              cutoff.isoformat(), day.isoformat()))
            sources.append(meta)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            rejected.append({"date": day.isoformat(), "error": str(exc)})
    return rows, rejected, {"calendar_days": len(days), "queried_days": len(selected),
                             "source_evidence": sources, "coverage_partial": len(selected) != len(days) or bool(rejected)}
