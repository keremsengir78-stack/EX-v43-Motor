"""Seal exact artifact files as content-addressed, append-only evidence."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


KINDS = {"ex-prospective-forecasts": "prematch-and-research",
         "ex-prospective-settlement": "settlement-and-performance",
         "ex-technical-audit": "technical-audit", "ex-official-source-probe": "official-source-probe", "ex-historical-facts": "historical-facts", "ex-frozen-research-candidates": "frozen-candidates",
         "ex-weekly-capacity": "weekly-capacity", "ucl-research-evidence": "ucl-domestic-research", "ex-retrospective-results": "retrospective-research"}


def artifact_base_name(name):
    batch = re.fullmatch(r"(ex-prospective-forecasts|ex-historical-facts)-\d{4}-\d{2}-\d{2}", name or "")
    return batch[1] if batch else name


def digest(data):
    return hashlib.sha256(data).hexdigest()


def insert(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(data)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError(f"Existing evidence differs: {path}")


def seal(store, source, receipt):
    meta = json.loads(receipt.read_bytes())
    kind = KINDS[artifact_base_name(meta["name"])]
    asset = meta["id"]
    if type(asset) is not int or asset < 1:
        raise ValueError("Invalid artifact ID")
    files = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlinks are not evidence files")
        if path.is_file():
            data = path.read_bytes()
            sha = digest(data)
            if not re.fullmatch(r"[a-zA-Z0-9_.\-/]+", path.relative_to(source).as_posix()):
                raise ValueError("Unrecognized artifact file path")
            insert(store / "objects" / sha[:2] / sha, data)
            files[path.relative_to(source).as_posix()] = sha
    if not files:
        raise ValueError("No source evidence files")
    # Keep only the receipt fields used for provenance. GitHub's download
    # URLs and its expired flag are mutable.
    index = {"receipt": {k: meta[k] for k in ("id", "name", "created_at", "digest")}, "files": files}
    insert(store / "records" / kind / f"{asset}.json",
           (json.dumps(index, sort_keys=True, indent=2) + "\n").encode())
    categories = ({"prematch": ("capture.json", "forecasts/capture.json", "pregame-cache/"),
                   "research-forecast": ("forecasts.jsonl", "forecasts/")}
                  if kind == "prematch-and-research" else {})
    if kind == "settlement-and-performance":
        categories = {"verified-outcome": ("outcomes.jsonl", "settlement/outcomes.jsonl",
                                           "settlement/tracked-verified-outcomes.jsonl"),
                      "settlement-source": ("settlement-cache/raw/",)}
    for category, prefixes in categories.items():
        selected = {name: sha for name, sha in files.items()
                    if any(name.startswith(key) if key.endswith("/") else name == key for key in prefixes)}
        if selected:
            typed = {**index, "files": selected}
            insert(store / "records" / category / f"{asset}.json",
                   (json.dumps(typed, sort_keys=True, indent=2) + "\n").encode())


def restore(store, kind, destination, limit=None, *, files=None):
    indexes = sorted((store / "records" / kind).glob("*.json"), key=lambda p: int(p.stem), reverse=True)
    for index in indexes[:limit]:
        record = json.loads(index.read_bytes())
        receipt = record["receipt"]
        if str(receipt["id"]) != index.stem or KINDS.get(artifact_base_name(receipt["name"])) != kind:
            raise ValueError("Evidence receipt does not match archive index")
        selected = {name: sha for name, sha in record["files"].items() if files is None or name in files}
        if not selected:
            continue
        target = destination / index.stem
        insert(target / "receipt.json", json.dumps(record["receipt"], sort_keys=True).encode())
        for name, sha in selected.items():
            parts = PurePosixPath(name)
            if parts.is_absolute() or ".." in parts.parts or not re.fullmatch(r"[a-f0-9]{64}", sha):
                raise ValueError("Unsafe archived evidence reference")
            data = (store / "objects" / sha[:2] / sha).read_bytes()
            if digest(data) != sha:
                raise ValueError("Archived evidence checksum mismatch")
            insert(target / name, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store", type=Path, required=True)
    cmd = p.add_subparsers(dest="mode", required=True)
    writer = cmd.add_parser("seal")
    writer.add_argument("--source", type=Path, required=True)
    writer.add_argument("--receipt", type=Path, required=True)
    reader = cmd.add_parser("restore")
    reader.add_argument("--kind", choices=KINDS.values(), required=True)
    reader.add_argument("--output", type=Path, required=True)
    reader.add_argument("--limit", type=int)
    reader.add_argument("--file", action="append")
    args = p.parse_args()
    if args.mode == "seal":
        seal(args.store, args.source, args.receipt)
    else:
        restore(args.store, args.kind, args.output, args.limit, files=args.file)


if __name__ == "__main__":
    main()
