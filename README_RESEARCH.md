# EX v4.3 Integrated Research Motor v1.1

A one-command local workflow, integrating prior ingestion and goal-model modules. Requires Python 3.10+; standard library only.

## Run

```bash
python ex_one_command.py --as-of 2026-11-21 --seasons 2025-26 2026-27 --leagues en.1 de.1 --outdir output
```

To use a downloaded OpenFootball mirror, add `--offline /path/to/mirror` with files like `2026-27/en.1.json`. To score upcoming matches, add `--fixtures fixtures.csv` with columns `date,league,home,away,season_start,previous_start`. Run `python -m unittest discover -v` for checks.

## Integrity rules

* A score dated on or after `--as-of` is excluded. Match dates in `--fixtures` before `--as-of` are rejected.
* No EX FINAL is authorized. Current baseline Poisson probabilities are **not** EX-G. Independent confirmation, market odds, context features, 50/30/20 calibrated model and trustworthy pre-match snapshots are missing.
* The source freshness gate is conservative: a season ending months ago will be marked stale. This is an intentionally safe limitation of the inherited ingestion component; distinguish historical archives from current season in a future revision.
* Alias resolution is explicit and league-scoped, not risky fuzzy auto-merge.
* A provider's newest published commit does not prove all individual match records are up-to-date.

## Data rights

OpenFootball football.json is CC0. Source: https://github.com/openfootball/football.json . It warns that upstream Football.TXT sources do not necessarily receive daily updates.
