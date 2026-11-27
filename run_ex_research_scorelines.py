"""Add a separate score coherence and PUP audit to an archived candidate run."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ex_research_scorelines import reconcile, research_pup, validation_order


def audit(archived, diagnostics):
    order = validation_order(archived["common_statistical_comparison"])
    results = []
    for row in archived["daily"]:
        candidates = row["candidates"]
        model = next((name for name in order if name in candidates), None)
        distributions = {name: reconcile(p) for name, p in candidates.items()}
        fixture = row["fixture"]
        prior_pup = row["pup"] or {}
        results.append({"fixture": fixture, "input_cutoff": row["cutoff"],
                        "source_sealed_at": row["source_sealed_at"], "validation_choice": model,
                        "probabilities": candidates, "scoreline_checks": distributions,
                        "research_pup": research_pup(candidates[model], distributions[model],
                                                     prior_pup.get("market_reasons", {})) if model else None,
                        "archived_reference_score_scenarios": row["score_scenarios_reference"],
                        "archived_tur2": row["archived_tur2"],
                        "archived_auto_control": row["archived_auto_control"],
                        "missing_inputs": row["missing_by_model"] if model is None else None,
                        "form_diagnostics": diagnostics.get(fixture["event_id"]) if model is None else None,
                        "ex_g": None, "ex_final_allowed": False})
    return {"validation_order": order, "fixtures": results,
            "primary_score_distributions": dict(Counter(
                row["scoreline_checks"][row["validation_choice"]]["status"]
                for row in results if row["validation_choice"])),
            "all_score_distributions": dict(Counter(check["status"] for row in results
                                                     for check in row["scoreline_checks"].values())),
            "pup": dict(Counter(row["research_pup"]["status"] for row in results if row["research_pup"])),
            "missing_form": sum(not row["validation_choice"] for row in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--optimization", type=Path, required=True)
    parser.add_argument("--daily", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.optimization.read_bytes()
    archived = json.loads(raw)
    diagnostics = {}
    for path in args.daily:
        evidence = path.read_bytes()
        if hashlib.sha256(evidence).hexdigest() not in archived["inputs_sha256"].values():
            raise ValueError("Daily source differs from the optimization archive")
        for row in json.loads(evidence):
            diagnostics[row["fixture"]["event_id"]] = row["domestic_diagnostics"]
    if set(diagnostics) != {row["fixture"]["event_id"] for row in archived["daily"]}:
        raise ValueError("Daily source does not cover the optimization archive")
    report = audit(archived, diagnostics)
    report.update(optimization_sha256=hashlib.sha256(raw).hexdigest(),
                  reviewed_at=datetime.now(timezone.utc).isoformat(),
                  scope="RESEARCH_ARCHIVE_AUDIT", production_allowed=False)
    with args.output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
