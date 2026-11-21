# EX v4.3 Research Engine: verification status

## Implemented in ex-v43-development

- OpenFootball results with score format validation and dated cutoff.
- Historical seasons treated as archives; the newest requested season retains a strict freshness check.
- Football-Data independent CSV score comparison (league/date/team matching, coverage and conflicts).
- Independent Poisson *baselines* for 2.5 UST, KG VAR, MS1, MSX, MS2.
- Explicit 50/30/20 evidence scoring module (ex_decision.py); blocks missing/unverified inputs and does **not** mislabel scores as calibrated probabilities.
- Regression tests for parsing, freshness, cross-source conflicts, probability normalization, fixture and odds gates.
- Strict fixture/odds input checks with the user-approved 1.19-or-lower PASS threshold; no invented snapshots.
- GitHub Actions audit artifacts and BLOCKED status on stale data.

## Run

```bash
python -m unittest discover -s tests -v
python ex_one_command.py --as-of 2026-11-21 --seasons 2025-26 2026-27 --leagues en.1 de.1 es.1 it.1 fr.1 --outdir ex_run
```

The second source is football-data.co.uk. Team aliases must be reviewed; unmatched records are **not** independently verified. Its results are compared, not silently substituted into the OpenFootball dataset. If a provider is unavailable, coverage is not assumed.

## Evidence input

Use `--odds odds.json` with a JSON array of odds snapshots in the same order as `--fixtures`. Each entry requires `decimal_odds`, `market`, `bookmaker`, `observed_at` (timezone-aware), and `source`. Fixture CSV requires `fixture_source` and `fixture_checked_at` for verification. These are validation inputs, not an automatic live odds/official fixture provider.

Use `--evidence evidence.json` to pass a JSON mapping each market (`2.5_UST`, `KG_VAR`, `MS1`, `MS2`) to `team_strength`, `match_conditions`, `external_factors`. Each input requires `score` in [0,1], `verified: true`, `source` and `timestamp`. This computes an auditable weighted score only, not a calibrated EX-G probability. No synthetic scores are inserted.

## Outstanding gates (EX FINAL not authorized)

1. OpenFootball active-season data may be stale; secondary verification alone does not refresh primary results.
2. Current official fixture and lineup-independent context, opponent-strength and external-factor feature inputs need timestamped sources.
3. The user-approved 50% strength / 30% match conditions / 20% external EX-G model requires specified, reproducible feature definitions, validation and calibration.
4. Odds snapshots, source-specific coverage, market lock, Tur-2 independent verification and Auto-Control are incomplete.
5. PUP is deferred until all three market families have been independently assessed.
6. The historical venue-weighted baseline requires sufficient data for each bucket; missing samples must not be presented as complete.

A successful CI run only proves that tests and configured data checks passed. It is not evidence of EX FINAL readiness. No EX FINAL picks should be issued by this code.
