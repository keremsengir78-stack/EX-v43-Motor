"""Capture bounded, immutable official league evidence for offline parsing."""

import argparse
import datetime as dt
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ex_history_archive import MAX_BYTES, atomic_write
from run_ex_official_minutes_batch import OFFICIAL_HOSTS


ALLOWED = frozenset().union(*OFFICIAL_HOSTS.values(), {"www.bundesliga.com"})


def checked(url):
    address = urlsplit(url)
    if address.scheme != "https" or address.netloc not in ALLOWED or address.fragment:
        raise ValueError("Unregistered official evidence URL")


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def capture(config, root):
    client = build_opener(OfficialRedirect)
    rows = {}
    for name, url in config.items():
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("Invalid source label")
        try:
            checked(url)
            with client.open(Request(url, headers={"User-Agent": "EX-v4.3 evidence audit"}), timeout=12) as response:
                raw = response.read(MAX_BYTES + 1)
                final_url = response.geturl()
                checked(final_url)
            if len(raw) > MAX_BYTES or not raw:
                raise ValueError("Invalid official evidence size")
            digest = sha256(raw).hexdigest()
            atomic_write(root / f"{digest}.html", raw)
        except (URLError, OSError, ValueError) as exc:
            rows[name] = {"url": url, "error": str(exc)}
        else:
            rows[name] = {"url": url, "final_url": final_url, "sha256": digest,
                          "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                          "bytes": len(raw)}
    atomic_write(root / "manifest.json", (json.dumps(rows, indent=2) + "\n").encode())
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(json.loads(args.config.read_text()), args.output)))


if __name__ == "__main__":
    main()
