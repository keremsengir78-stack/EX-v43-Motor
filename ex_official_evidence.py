"""Validate manually observed official fixture evidence; never auto-certify EX FINAL."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED = {"de.1": "datencenter.dfb.de", "es.1": "iaas-public-front-pro.laliga.com"}


def validate_evidence(document):
    if not isinstance(document, dict):
        raise ValueError("official evidence document must be an object")
    if document.get("ex_final_allowed") is not False:
        raise ValueError("official evidence cannot certify EX FINAL")
    if document.get("status") != "MANUAL_OFFICIAL_SOURCE_EVIDENCE_NOT_MERGED":
        raise ValueError("unexpected evidence state")
    cutoff_value = document.get("as_of")
    if not isinstance(cutoff_value, str):
        raise ValueError("invalid cutoff")
    cutoff = dt.date.fromisoformat(cutoff_value)
    records = document.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("empty evidence")
    seen = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid evidence record")
        league = row.get("league")
        if not isinstance(league, str) or league not in ALLOWED:
            raise ValueError("unapproved league")
        date_value = row.get("date")
        if not isinstance(date_value, str):
            raise ValueError("invalid fixture date")
        date = dt.date.fromisoformat(date_value)
        if date >= cutoff:
            raise ValueError("evidence at or after cutoff")
        source = row.get("source_url")
        if not isinstance(source, str) or any(ch.isspace() for ch in source):
            raise ValueError("invalid source URL")
        try:
            url = urlsplit(source)
            valid_url = (url.scheme == "https" and url.hostname == ALLOWED[league]
                         and url.username is None and url.password is None
                         and url.port in (None, 443) and not url.fragment)
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError("unapproved official evidence domain")
        if row.get("verification_status") != "OFFICIAL_RESULT_OBSERVED_NOT_CROSS_MERGED":
            raise ValueError("evidence falsely certified")
        home, away = row.get("home"), row.get("away")
        if (not isinstance(home, str) or not home.strip() or
                not isinstance(away, str) or not away.strip() or
                home.strip().casefold() == away.strip().casefold()):
            raise ValueError("invalid fixture identity")
        if any(type(row.get(k)) is not int or not 0 <= row[k] <= 30
               for k in ("home_goals", "away_goals")):
            raise ValueError("invalid score")
        key = (league, date, row["home"], row["away"])
        if key in seen:
            raise ValueError("duplicate evidence")
        seen.add(key)
    return {"records": len(records), "ex_final_allowed": False,
            "status": "OFFICIAL_EVIDENCE_FORMAT_VALID_NOT_CROSS_MERGED"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="evidence/official_unresolved_2026_11.json")
    args = parser.parse_args()
    print(json.dumps(validate_evidence(json.loads(Path(args.input).read_text()))))


if __name__ == "__main__":
    main()
