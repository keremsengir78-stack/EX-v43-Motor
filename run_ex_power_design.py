"""Register a fixed prospective window using independent pilot-week loss differences."""

import argparse
import datetime as dt
import json
from pathlib import Path

from ex_history_archive import atomic_write, utc
from ex_prospective_power import plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pilot", type=Path, required=True)
    p.add_argument("--target-gain", type=float, required=True)
    p.add_argument("--family-alpha", type=float, required=True)
    p.add_argument("--power", type=float, required=True)
    p.add_argument("--holdout-start", required=True)
    p.add_argument("--holdout-end", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    registered = dt.datetime.now(dt.timezone.utc)
    start, end = utc(args.holdout_start), utc(args.holdout_end)
    if not registered <= start < end:
        p.error("Register the design before the holdout starts")
    design = plan(json.loads(args.pilot.read_text()), args.target_gain, args.family_alpha,
                  args.power, comparisons=10)
    design.update(registered_at=registered.isoformat(), holdout_start=start.isoformat(),
                  holdout_end=end.isoformat(), production_allowed=False)
    atomic_write(args.output, (json.dumps(design, indent=2) + "\n").encode())
    print(json.dumps(design))


if __name__ == "__main__":
    main()
