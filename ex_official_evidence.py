"""Validate manually observed official fixture evidence; never auto-certify EX FINAL."""
import datetime as dt
import json
from pathlib import Path

ALLOWED = {"de.1": "datencenter.dfb.de", "es.1": "iaas-public-front-pro.laliga.com"}


def validate_evidence(document):
    if document.get("ex_final_allowed") is not False:
        raise ValueError("official evidence cannot certify EX FINAL")
    if document.get("status") != "MANUAL_OFFICIAL_SOURCE_EVIDENCE_NOT_MERGED":
        raise ValueError("unexpected evidence state")
    cutoff = dt.date.fromisoformat(document["as_of"])
    records = document.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("empty evidence")
    seen = set()
    for row in records:
        league = row["league"]
        date = dt.date.fromisoformat(row["date"])
        if date >= cutoff:
            raise ValueError("evidence at or after cutoff")
        from urllib.parse import urlsplit
        url = urlsplit(row["source_url"])
        if url.scheme != "https" or url.hostname != ALLOWED.get(league):
            raise ValueError("unapproved official evidence domain")
        if row.get("verification_status") != "OFFICIAL_RESULT_OBSERVED_NOT_CROSS_MERGED":
            raise ValueError("evidence falsely certified")
        if not row["home"].strip() or not row["away"].strip() or row["home"] == row["away"]:
            raise ValueError("invalid fixture identity")
        if any(type(row[k]) is not int or not 0 <= row[k] <= 30
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
