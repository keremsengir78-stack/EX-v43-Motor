"""Seal exact artifact files as content-addressed, append-only evidence."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


KINDS = {"ex-prospective-forecasts": "prematch-and-research",
         "ex-prospective-settlement": "settlement-and-performance"}


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
    kind = KINDS[meta["name"]]
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


def restore(store, kind, destination, limit=None):
    indexes = sorted((store / "records" / kind).glob("*.json"), key=lambda p: int(p.stem), reverse=True)
    for index in indexes[:limit]:
        record = json.loads(index.read_bytes())
        target = destination / index.stem
        insert(target / "receipt.json", json.dumps(record["receipt"], sort_keys=True).encode())
        for name, sha in record["files"].items():
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
    args = p.parse_args()
    if args.mode == "seal":
        seal(args.store, args.source, args.receipt)
    else:
        restore(args.store, args.kind, args.output, args.limit)


if __name__ == "__main__":
    main()
