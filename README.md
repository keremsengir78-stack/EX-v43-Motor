# EX v4.3 Motor

EX v4.3 football analysis engine, under development. This repository does **not** currently produce approved EX FINAL predictions.

## Development and verification

- Active development branch: `ex-v43-development`. Do not merge into `main` without explicit approval.
- GitHub Actions: `.github/workflows/ex-v43-regression.yml`, triggered by development-branch pushes and pull requests.
- Checks: Python syntax, isolated `tests/test_safety_gates.py`, then all `tests/test*.py` via unittest discovery.
- CI commit statuses: `ex-v43/syntax`, `ex-v43/safety`, `ex-v43/full`, `ex-v43/regression`. On full-regression failures, `ex-v43/failing-test/...` exposes the first reported failing test.
- Last confirmed all-green CI commit when this document was written: `0b06310cd0a799ee22eddd13bdb6af9aefafa125`. Check the latest commit status before relying on a newer revision.

## Safety contract

- `ex_decision.py`: evidence weighting is 50% team strength, 30% match conditions, 20% external factors. Weighted evidence scores are **not** calibrated probabilities.
- `ex_fixture_odds.py`: audited fixture and odds inputs, timestamp cutoffs, and the odds-at-or-below-1.19 PASS rule.
- `ex_auto_control.py`: deterministic snapshot and Tur-2 consistency checks. Only `INGESTED_CROSS_VERIFIED` is accepted as a verified ingestion state; at least two independent sources are required.
- Fixture verification, odds verification, and reproducible calculations do **not** independently establish data-source independence or model calibration.
- `ex_final_allowed` remains **false** until historical samples, independently calibrated market probabilities, match context, PUP, and all mandatory checks have been implemented and independently verified. Never promote `BASELINE_ONLY` to EX FINAL.

## Run checks locally

```bash
python -m compileall -q .
python -m unittest discover -s tests -p 'test_safety_gates.py' -v
python -m unittest discover -s tests -p 'test*.py' -v
```

GitHub CI passing means the checked tests passed for that commit; it does not establish prediction accuracy or EX FINAL readiness.
