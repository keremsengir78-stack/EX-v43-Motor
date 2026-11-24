"""Parse UEFA team news without assigning unverified player impact."""

import re
from html import unescape

from ex_cross_verify import norm


def _plain(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", html)).replace("\ufeff", "").split())


def parse_team_news(raw):
    parts = re.split(r"(<h4>.*?</h4>)", raw.decode("utf-8"), flags=re.S)
    matches = {}
    for heading, body in zip(parts[1::2], parts[2::2]):
        match = re.search(r"/match/(\d+)--[^\"]+\"[^>]*>([^<]+)</a>", heading)
        if not match or " vs " not in match[2]:
            continue
        # The heading binds each two-team lineup preview to its fixture.
        sides = []
        for paragraph in re.findall(r"<p>(.*?)</p>", body, flags=re.S):
            fields = [_plain(part).partition(": ") for part in re.split(r"<br\s*/?>", paragraph)]
            values = {label: value for label, sep, value in fields if sep}
            if "Out" in values and "Doubtful" in values and fields[0][1]:
                sides.append({
                    "reported_team": fields[0][0], "predicted_lineup": fields[0][2],
                    "out": values["Out"], "doubtful": values["Doubtful"],
                    "suspension_risk": values.get("Misses next match if booked"),
                })
        if len(sides) == 2:
            key = tuple(norm(team) for team in unescape(match[2]).split(" vs "))
            if key in matches:
                raise ValueError("Duplicate UEFA team news fixture")
            matches[key] = {"uefa_match_id": match[1], "home": sides[0], "away": sides[1]}
    return matches
