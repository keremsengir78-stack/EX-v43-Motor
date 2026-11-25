"""Dispatch archive operations on the development ref from an external scheduler."""

import argparse
import datetime as dt
import subprocess

REPO = "keremsengir78-stack/EX-v43-Motor"
REF = "ex-v43-ucl-research-verification"


def commands(day, weekly):
    common = ["--repo", REPO, "--ref", REF]
    if weekly:
        prior_monday = day - dt.timedelta(days=day.weekday() + 7)
        return [["gh", "workflow", "run", "ex-weekly-evidence.yml", *common,
                 "-f", f"week_start={prior_monday}", "-f", "persist_inventory=true"]]
    return [["gh", "workflow", "run", "ex-prospective-operations.yml", *common,
             "-f", f"mode={'cycle' if offset == 0 else 'capture'}", "-f", f"day={day + dt.timedelta(days=offset)}"]
            for offset in range(3)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    for command in commands(dt.datetime.now(dt.timezone.utc).date(), args.weekly):
        if args.execute:
            subprocess.run(command, check=True)
        else:
            print(" ".join(command))


if __name__ == "__main__":
    main()
