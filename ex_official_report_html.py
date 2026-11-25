"""Extract nominal regulation minutes from official league HTML templates."""

from collections import Counter
from html import unescape
import re

from ex_official_minutes import minutes_from_timeline


def plain(value):
    return " ".join(unescape(re.sub(r"<[^>]*>", "", value)).split())


def nominal_minute(value):
    # Published stoppage time falls on the boundary of the corresponding half.
    match = re.fullmatch(r"(\d{1,2})(?:\s*\+\s*\d{1,2})?\s*[’'“]?", value)
    if not match or int(match[1]) > 90:
        raise ValueError("Unrecognized regulation minute")
    return int(match[1])


def ukrainian_minutes(html):
    if re.search(r'class="event type-card-(?:2|3)"', html):
        raise ValueError("Dismissals require review")
    lineups = re.findall(r'class="list-title">\s*Line-ups\s*</div>(.*?)'
                         r'class="list-title">\s*Substitutes', html, flags=re.S)
    if len(lineups) != 2:
        raise ValueError("Expected two UPL starting lineups")
    def player(value):
        return re.sub(r"\s+\(C\)$", "", plain(value), flags=re.I)

    starters = [[player(name) for name in re.findall(r'class="player-name">(.*?)</div>', segment, re.S)]
                for segment in lineups]
    changes = [[], []]
    substitutions = []
    events = re.split(r'(?=<div class="event [^"]+">)', html)
    for event in events:
        if not event.startswith('<div class="event type-change">'):
            continue
        players = re.findall(r'class="players">(.*?)</div>', event, re.S)
        point = re.search(r'class="point">(.*?)</div>', event, re.S)
        if len(players) != 1 or not point:
            raise ValueError("Incomplete UPL change")
        names = [player(name) for name in re.split(r"<br\s*/?>", players[0])]
        if len(names) != 2:
            raise ValueError("UPL change requires two players")
        substitutions.append((nominal_minute(plain(point[1])), names))
    active = [set(group) for group in starters]
    appeared = [group.copy() for group in active]
    for minute, names in sorted(substitutions, key=lambda event: event[0]):
        applicable = [(i, outgoing, incoming) for i, group in enumerate(active)
                      for outgoing, incoming in (names, names[::-1])
                      if outgoing in group and incoming not in appeared[i]]
        if len(applicable) != 1:
            raise ValueError("Cannot identify UPL substitution team")
        i, outgoing, incoming = applicable[0]
        active[i].remove(outgoing)
        active[i].add(incoming)
        appeared[i].add(incoming)
        changes[i].append((minute, outgoing, incoming))
    return {side: minutes_from_timeline(starters[i], sorted(changes[i], key=lambda row: row[0]))
            for i, side in enumerate(("home", "away"))}


def slovak_minutes(html):
    candidates = []
    for table in re.findall(r"<table\b.*?</table>", html, re.S):
        rows = re.findall(r'<td class="sub">(.*?)</td>(?:(?!</tr>).)*?'
                          r'<td class="name"><a href="/hrac/([^"]+)">([^<]+)</a></td>', table, re.S)
        if not rows:
            continue
        if re.search(r'ico-card\s+(?:red|yellow-red)', table):
            raise ValueError("Dismissals require review")
        result, arrivals, departures = {}, Counter(), Counter()
        starters = 0
        for cell, player, name in rows:
            if player in result:
                raise ValueError("Duplicate Niké liga player")
            if not cell.strip():
                if starters < 11:
                    starters += 1
                    result[player] = {"name": plain(name), "minutes": 90}
                continue
            marks = re.findall(r'ico-sub-(in|out)" title="([^"]+)"', cell)
            if len(marks) != 1:
                raise ValueError("Unexpected Niké liga substitution token")
            direction, title = marks[0]
            minute = nominal_minute(title.split(".", 1)[0])
            if direction == "out":
                starters += 1
                departures[minute] += 1
            else:
                arrivals[minute] += 1
            result[player] = {"name": plain(name), "minutes": minute if direction == "out" else 90 - minute}
        candidates.append((starters, arrivals, departures, result))
    output = {}
    # Some pages render starters and bench in separate consecutive tables.
    combined = []
    for starters, arrivals, departures, rows in candidates:
        if starters == 11:
            combined.append((arrivals, departures, rows))
        elif starters == 0 and combined:
            previous_in, previous_out, previous_rows = combined[-1]
            if previous_rows.keys() & rows.keys():
                raise ValueError("Duplicate Niké liga player")
            combined[-1] = (previous_in + arrivals, previous_out + departures, previous_rows | rows)
        else:
            raise ValueError("Unrecognized Niké liga lineup layout")
    for side, (arrivals, departures, rows) in zip(("home", "away"), combined):
        if arrivals != departures or sum(row["minutes"] for row in rows.values()) != 990:
            raise ValueError("Unbalanced Niké liga substitution minutes")
        output[side] = rows
    if len(combined) != 2:
        raise ValueError("Expected two Niké liga lineups")
    return output
