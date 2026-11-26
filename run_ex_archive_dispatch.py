"""Dispatch archive operations on the development ref from an external scheduler."""

import argparse
import datetime as dt
import json
from urllib.parse import urlencode

from ex_evidence_store import KINDS, artifact_base_name
import subprocess

REPO = "keremsengir78-stack/EX-v43-Motor"
REF = "ex-v43-ucl-research-verification"


def commands(day, weekly, offset=None):
    common = ["--repo", REPO, "--ref", REF]
    if weekly:
        prior_monday = day - dt.timedelta(days=day.weekday() + 7)
        return [["gh", "workflow", "run", "ex-weekly-evidence.yml", *common,
                 "-f", f"week_start={prior_monday}", "-f", "persist_inventory=true"]]
    return [["gh", "workflow", "run", "ex-prospective-operations.yml", *common,
             "-f", f"mode={'cycle' if offset == 0 else 'capture'}", "-f", f"day={day + dt.timedelta(days=offset)}"]
            for offset in (range(3) if offset is None else (offset,))]


RECOVERABLE = {
    "ex-prospective-operations.yml": {"ex-prospective-forecasts", "ex-prospective-settlement", "ex-historical-facts"},
    "ex-weekly-evidence.yml": {"ex-weekly-capacity"},
}


def api(endpoint, *, pages=False):
    command = ["gh", "api", endpoint]
    if pages:
        command.append("--paginate")
    payload = subprocess.check_output(command, text=True)
    if not pages:
        return json.loads(payload)
    decoder = json.JSONDecoder()
    results = []
    while payload.strip():
        page, end = decoder.raw_decode(payload.lstrip())
        results.append(page)
        payload = payload.lstrip()[end:]
    return results


def missing_artifacts(since, request=api):
    """Compare trusted workflow artifacts with the durable archive index."""
    base = f"repos/{REPO}"
    categories = request(f"{base}/contents/records?ref=ex-evidence-archive")
    by_kind = {}
    available = sorted({name for names in RECOVERABLE.values() for name in names})
    index = {row["name"]: row["sha"] for row in categories if row["type"] == "dir"}
    for name in available:
        sha = index.get(KINDS[name])
        if sha:
            tree = request(f"{base}/git/trees/{sha}")
            if tree.get("truncated"):
                raise ValueError(f"Archive index is truncated for {name}")
            by_kind[name] = {entry["path"] for entry in tree["tree"] if entry["type"] == "blob"}
    missing, expired = set(), set()
    for workflow, names in RECOVERABLE.items():
        query = urlencode({"branch": REF, "status": "completed", "created": f">={since}", "per_page": 100})
        for page in request(f"{base}/actions/workflows/{workflow}/runs?{query}", pages=True):
            for run in page["workflow_runs"]:
                if run["event"] not in {"workflow_dispatch", "schedule"} or run["head_branch"] != REF:
                    continue
                for result in request(f"{base}/actions/runs/{run['id']}/artifacts?per_page=100", pages=True):
                    for artifact in result["artifacts"]:
                        name, asset = artifact_base_name(artifact["name"]), artifact["id"]
                        if name not in names or f"{asset}.json" in by_kind.get(name, set()):
                            continue
                        if artifact["expired"]:
                            expired.add(asset)
                        elif artifact.get("digest", "").startswith("sha256:"):
                            missing.add(asset)
    return sorted(missing), sorted(expired)


def recovery_commands(day, assets):
    monday = day - dt.timedelta(days=day.weekday())
    return [["gh", "workflow", "run", "ex-weekly-evidence.yml", "--repo", REPO, "--ref", REF,
             "-f", f"week_start={monday}", "-f", "preserve_only=true",
             "-f", "artifact_ids=" + ",".join(map(str, assets[i:i + 4]))]
            for i in range(0, len(assets), 4)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--weekly", action="store_true")
    mode.add_argument("--recover-since", type=dt.date.fromisoformat, help="Scan completed archive runs since a UTC date")
    parser.add_argument("--offset", type=int, choices=range(3), help="Dispatch only one UTC date")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if (args.weekly or args.recover_since) and args.offset is not None:
        parser.error("--offset applies to daily jobs")
    today = dt.datetime.now(dt.timezone.utc).date()
    if args.recover_since:
        if args.recover_since > today:
            parser.error("--recover-since must be today or earlier")
        missing, expired = missing_artifacts(args.recover_since)
        print(json.dumps({"missing": missing, "expired": expired}))
        planned = recovery_commands(today, missing)
    else:
        planned = commands(today, args.weekly, args.offset)
    for command in planned:
        if args.execute:
            subprocess.run(command, check=True)
        else:
            print(" ".join(command))


if __name__ == "__main__":
    main()
