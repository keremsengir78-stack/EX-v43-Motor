"""Replay the source-origin audit of a sealed, exact historical form join."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from ex_espn_provider import ESPN_LEAGUES
from ex_history_archive import atomic_write, utc
from ex_history_sources import ESPN, match_detail
from ex_retrospective import settled_facts


ATTRIBUTION_FIELDS = {"attribution", "copyright", "dataprovider", "dataproviders",
                      "provider", "providers", "datasource", "sourcecredit", "credit"}


def attribution_fields(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("_", "").replace("-", "")
            if normalized in ATTRIBUTION_FIELDS and isinstance(child, (str, dict, list)):
                yield ".".join((*path, key)), child
            else:
                yield from attribution_fields(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from attribution_fields(child, (*path, str(index)))


def review(prior, official_store, captures, documentation):
    events, uses = {}, []
    official_digests = {}
    for row in prior["form_window_date_candidates"]:
        fixture = row["historical_fixture"]
        event = fixture["event_id"]
        if event not in events:
            league = fixture["league"]
            slug = ESPN_LEAGUES[league]
            source = fixture["official_source"]
            digest = source["sha256"]
            if digest not in official_digests:
                raw = (official_store / digest[:2] / digest).read_bytes()
                if sha256(raw).hexdigest() != digest or len(raw) != source["size"]:
                    raise ValueError("Official source bytes do not match the archived locator")
                official_digests[digest] = len(raw)
            path = captures / f"espn-{event}.json"
            fresh = path.read_bytes()
            stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            identity = {"event_id": event, "kickoff_at": fixture["kickoff_at"],
                        "teams": fixture["team_ids"], "competition": slug}
            match_detail(fresh, stamp, identity)
            payload = json.loads(fresh)
            if payload["header"].get("league", {}).get("slug") != slug:
                raise ValueError(f"Fresh primary league disagrees for {event}")
            fact = settled_facts(payload, identity, stamp.isoformat())
            if fact["score"] != tuple(fixture["score"]):
                raise ValueError(f"Fresh primary score disagrees for {event}")
            fields = dict(attribution_fields({key: payload[key] for key in ("header", "meta", "keyEvents")
                                              if key in payload}))
            events[event] = {**fixture, "primary_archive_seal": row["primary_archive_seal"],
                             "primary_recheck": {"url": f"{ESPN}/{slug}/summary?event={event}",
                                                 "observed_at": stamp.isoformat(), "sha256": sha256(fresh).hexdigest(),
                                                 "attribution_fields": fields,
                                                 "same_bytes_as_historical_primary":
                                                     sha256(fresh).hexdigest() == fixture["provider_sha256"]},
                             "documentation": documentation[league],
                             "status": "BLOCKED_SOURCE_LINEAGE_UNPROVEN"}
        elif any(events[event][key] != value for key, value in fixture.items()):
            raise ValueError(f"Inconsistent historical source identity for {event}")
        if (not row["reproduced_form_windows"]
                or utc(events[event]["official_sealed_at"]) >= utc(row["decision_cutoff"])):
            raise ValueError(f"Form join lacks pre-cutoff official evidence for {event}")
        uses.append({"event_id": event, "target": row["target"], "side": row["side"],
                     "as_of": row["decision_cutoff"], "windows": row["reproduced_form_windows"],
                     "status": events[event]["status"]})
    if len({(row["event_id"], row["target"], row["side"]) for row in uses}) != len(uses):
        raise ValueError("Duplicate historical form use")
    return {"events": list(events.values()), "form_uses": uses, "unique_target_matches": len({r["target"] for r in uses}),
            "attribution_field_counts": dict(Counter(bool(r["primary_recheck"]["attribution_fields"]) for r in events.values())),
            "production_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("input", "objects", "captures", "documentation", "output"):
        parser.add_argument(f"--{field}", type=Path, required=True)
    args = parser.parse_args()
    result = review(json.loads(args.input.read_bytes()), args.objects, args.captures,
                    json.loads(args.documentation.read_bytes()))
    atomic_write(args.output, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
