import os
import json
from pathlib import Path
status={"ingest_step":os.environ.get("INGEST", ""),
        "review_step":os.environ.get("REVIEW", ""),
        "shadow_step":os.environ.get("SHADOW", ""),
        "offline_shadow_step":os.environ.get("OFFLINE_SHADOW", ""),
        "expanded_shadow_step":os.environ.get("EXPANDED_SHADOW", ""),
        "other_leagues_step":os.environ.get("OTHER_LEAGUES", ""),
        "other_shadow_step":os.environ.get("OTHER_SHADOW", ""),
        "source_audit_exists":Path("ex_run/audit.json").is_file(),
        "summary_exists":Path("ex_run/secondary_review_summary.json").is_file(),
        "germany_csv_exists":Path("ex_run/germany_unresolved_review.csv").is_file(),
        "ex_final_allowed":False,
        "commit":os.environ.get("GITHUB_SHA", ""),
        "run_id":os.environ.get("GITHUB_RUN_ID", "")}
audit=Path("ex_run/audit.json")
if audit.is_file():
    try:
        data=json.loads(audit.read_text(encoding="utf-8"))
        status["audit_status"]=data.get("status")
        status["source_errors"]=data.get("secondary_source_errors",[])
        # Publish raw baseline audit reasons separately from scoped strict reconciliations.
        # These fields are diagnostics, never independent approval evidence.
        status["baseline_blocking_sources"]=data.get("blocking_sources",[])
        status["baseline_secondary_unverified"]=data.get("secondary_unverified")
        status["baseline_secondary_conflicts"]=data.get("secondary_conflicts")
        status["baseline_newer_unverified_results"]=data.get("secondary_newer_unverified_results")
        status["baseline_unmatched_by_season"]=data.get("secondary_unmatched_by_season",{})
    except (ValueError, OSError) as exc:
        status["audit_read_error"]=str(exc)
shadow_path=Path("ex_run/germany_shadow_comparison.json")
status["shadow_comparison_exists"]=shadow_path.is_file()
if status["summary_exists"] and status["germany_csv_exists"]:
    try:
        summary=json.loads(Path("ex_run/secondary_review_summary.json").read_text(encoding="utf-8"))
        if summary.get("ex_final_allowed") is not False:
            raise ValueError("EX FINAL lock not explicit")
        status["unmatched_total"]=summary["unmatched_total"]
        status["germany_unmatched"]=summary["germany_unmatched"]
        Path("reports/latest_secondary_review_summary.json").write_bytes(
            Path("ex_run/secondary_review_summary.json").read_bytes())
        Path("reports/latest_germany_unresolved_review.csv").write_bytes(
            Path("ex_run/germany_unresolved_review.csv").read_bytes())
        status["evidence_published"]=True
        offline_path=Path("ex_run/germany_offline_shadow.json")
        if offline_path.is_file():
            offline=json.loads(offline_path.read_text(encoding="utf-8"))
            if offline.get("ex_final_allowed") is not False or offline.get("verified_score_matches_added") != 0:
                raise ValueError("Unsafe offline candidate evidence")
            Path("reports/latest_germany_offline_shadow.json").write_bytes(offline_path.read_bytes())
            status["germany_name_only_candidates"]=offline.get("unique_name_only_candidates")
        remaining_path=Path("ex_run/germany_shadow_remaining.json")
        if remaining_path.is_file():
            remaining=json.loads(remaining_path.read_text(encoding="utf-8"))
            if remaining.get("ex_final_allowed") is not False or remaining.get("aliases_approved") is not False:
                raise ValueError("Unsafe remaining shadow evidence")
            Path("reports/latest_germany_shadow_remaining.json").write_bytes(remaining_path.read_bytes())
            status["germany_shadow_remaining_count"]=remaining["unmatched_total"]
        new_candidates_path=Path("ex_run/germany_remaining_candidates.json")
        if new_candidates_path.is_file():
            new_candidates=json.loads(new_candidates_path.read_text(encoding="utf-8"))
            if new_candidates.get("ex_final_allowed") is not False or new_candidates.get("score_verified") is not False:
                raise ValueError("Unsafe remaining alias candidate evidence")
            Path("reports/latest_germany_remaining_candidates.json").write_bytes(new_candidates_path.read_bytes())
            status["germany_remaining_alias_candidates"]=len(new_candidates["candidates"])
            status["germany_remaining_candidate_names"]=[
                {"primary":row["primary_name"],"secondary":row["secondary_name"]}
                for row in new_candidates["candidates"]
            ]
            status["germany_candidates_approved"]=False
        german_strict_path=Path("ex_run/germany_strict_score_reconcile.json")
        if german_strict_path.is_file():
            german_strict=json.loads(german_strict_path.read_text(encoding="utf-8"))
            expected=status.get("germany_shadow_remaining_count")
            if (german_strict.get("ex_final_allowed") is not False
                    or type(german_strict.get("confirmed")) is not int
                    or type(german_strict.get("remaining")) is not int
                    or german_strict["confirmed"]+german_strict["remaining"]!=expected):
                raise ValueError("Unsafe German strict score reconciliation")
            Path("reports/latest_germany_strict_score_reconcile.json").write_bytes(german_strict_path.read_bytes())
            status["germany_strict_score_confirmed"]=german_strict["confirmed"]
            status["germany_strict_score_remaining"]=german_strict["remaining"]
            status["germany_strict_score_scope"]="german_shadow_remainder_only"
        queue_path=Path("ex_run/multileague_review_queue.json")
        if queue_path.is_file():
            queue=json.loads(queue_path.read_text(encoding="utf-8"))
            if queue.get("ex_final_allowed") is not False or queue.get("score_verified") is not False:
                raise ValueError("Unsafe review queue")
            if queue.get("total_review_queue")!=status["unmatched_total"]-status["germany_unmatched"]:
                raise ValueError("Review queue total mismatch")
            Path("reports/latest_multileague_review_queue.json").write_bytes(queue_path.read_bytes())
            status["non_germany_review_queue_published"]=True
        diagnostics_path=Path("ex_run/multileague_diagnostics.json")
        if diagnostics_path.is_file():
            diagnostics=json.loads(diagnostics_path.read_text(encoding="utf-8"))
            if diagnostics.get("ex_final_allowed") is not False or diagnostics.get("score_verified") is not False:
                raise ValueError("Unsafe multi-league diagnostics")
            if diagnostics.get("unmatched_total")!=status["unmatched_total"]-status["germany_unmatched"]:
                raise ValueError("Diagnostic total mismatch")
            Path("reports/latest_multileague_diagnostics.json").write_bytes(diagnostics_path.read_bytes())
            status["non_germany_diagnostics_published"]=True
            if queue_path.is_file():
                from ex_multileague_queue_validation import validate
                validated_queue=validate(queue,diagnostics)
                Path("reports/latest_multileague_queue_validated.json").write_text(
                    json.dumps(validated_queue,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
                status["non_germany_queue_validated"]=True
        multi_path=Path("ex_run/multileague_alias_candidates.json")
        if multi_path.is_file():
            multi=json.loads(multi_path.read_text(encoding="utf-8"))
            if multi.get("ex_final_allowed") is not False or multi.get("score_verified") is not False or multi.get("aliases_approved") is not False:
                raise ValueError("Unsafe multi-league alias report")
            if multi.get("non_germany_unmatched")!=status["unmatched_total"]-status["germany_unmatched"]:
                raise ValueError("Non-German unmatched totals disagree")
            Path("reports/latest_multileague_alias_candidates.json").write_bytes(multi_path.read_bytes())
            status["non_germany_alias_candidates"]=multi["candidate_count"]
        batch_total=json.loads(Path("ex_run/multileague_review_batches.json").read_text(encoding="utf-8"))["total_unmatched"]
        unique_path=Path("ex_run/multileague_unique_candidates.json")
        if unique_path.is_file():
            unique_report=json.loads(unique_path.read_text(encoding="utf-8"))
            if unique_report.get("total_fixtures")!=batch_total or unique_report.get("ex_final_allowed") is not False or unique_report.get("independently_verified_added")!=0:
                raise ValueError("Unsafe unique source candidates")
            Path("reports/latest_multileague_unique_candidates.json").write_bytes(unique_path.read_bytes())
            status["non_germany_unique_candidates_published"]=True
            status["unique_name_candidates"]=unique_report["unique_name_candidates"]
            status["remaining_for_manual_review"]=unique_report["remaining_for_manual_review"]
        score_audit_path=Path("ex_run/multileague_candidate_score_audit.json")
        if not score_audit_path.is_file():
            raise ValueError("Missing candidate score agreement audit")
        score_audit=json.loads(score_audit_path.read_text(encoding="utf-8"))
        if (score_audit.get("total_candidates")!=status["unique_name_candidates"]
                or score_audit.get("independently_verified_added")!=0
                or score_audit.get("ex_final_allowed") is not False):
            raise ValueError("Unsafe candidate score agreement audit")
        Path("reports/latest_multileague_candidate_score_audit.json").write_bytes(score_audit_path.read_bytes())
        status["candidate_score_agreement_counts"]=score_audit["counts"]
        strict_path=Path("ex_run/multileague_strict_score_reconcile.json")
        if not strict_path.is_file():
            raise ValueError("Missing strict score reconciliation")
        strict=json.loads(strict_path.read_text(encoding="utf-8"))
        if strict["total"]!=batch_total or strict["confirmed"]+strict["remaining"]!=strict["total"] or strict["ex_final_allowed"] is not False:
            raise ValueError("Unsafe strict score reconciliation")
        Path("reports/latest_multileague_strict_score_reconcile.json").write_bytes(strict_path.read_bytes())
        status["strict_score_confirmed"]=strict["confirmed"]
        status["strict_score_remaining"]=strict["remaining"]
        # Strict reconciliation is a scoped review batch, not a global EX FINAL approval.
        status["strict_score_scope"]="non_german_review_batches"
        status["strict_score_batch_complete"]=(strict["remaining"]==0)
        status["global_audit_blocked"]=(status.get("audit_status")!="READY")
        status["remaining_review_scope_note"]="Legacy unmatched and shadow counts are separate from strict score batch"
        status["ex_final_allowed"]=False
        for required in ("ex_run/multileague_source_candidates.json", "ex_run/multileague_candidate_summary.json", "ex_run/multileague_unique_candidates.json"):
            if not Path(required).is_file():
                raise ValueError("Missing required source matching output: "+required)
        summary_path=Path("ex_run/multileague_candidate_summary.json")
        if summary_path.is_file():
            candidate_summary=json.loads(summary_path.read_text(encoding="utf-8"))
            if candidate_summary.get("total_fixtures")!=batch_total or candidate_summary.get("ex_final_allowed") is not False or candidate_summary.get("independently_verified_added")!=0:
                raise ValueError("Unsafe candidate summary")
            Path("reports/latest_multileague_candidate_summary.json").write_bytes(summary_path.read_bytes())
            status["non_germany_candidate_summary_published"]=True
            status["candidate_same_day_found"]=candidate_summary["with_candidates"]
            status["candidate_same_day_missing"]=candidate_summary["without_candidates"]
            status["candidate_high_similarity"]=candidate_summary["high_name_similarity_candidates"]
            status["candidate_by_league"]=candidate_summary["by_league"]
        candidate_path=Path("ex_run/multileague_source_candidates.json")
        if candidate_path.is_file():
            candidate_report=json.loads(candidate_path.read_text(encoding="utf-8"))
            if candidate_report.get("total_fixtures")!=batch_total or candidate_report.get("ex_final_allowed") is not False or candidate_report.get("independently_verified_added")!=0:
                raise ValueError("Unsafe or incomplete source candidate report")
            Path("reports/latest_multileague_source_candidates.json").write_bytes(candidate_path.read_bytes())
            status["non_germany_source_candidates_published"]=True
        evidence_path=Path("ex_run/multileague_evidence_ledger_batch1.json")
        if evidence_path.is_file():
            evidence=json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence.get("ex_final_allowed") is not False or evidence.get("independently_verified_added")!=0:
                raise ValueError("Unsafe independent evidence ledger")
            if evidence.get("batch_id")!=1 or evidence.get("total_records")!=50:
                raise ValueError("Evidence ledger batch one incomplete")
            if any(r.get("score_confirmed") is not False or r.get("independent_source_url") is not None for r in evidence["records"]):
                raise ValueError("Fabricated evidence")
            Path("reports/latest_multileague_evidence_ledger_batch1.json").write_bytes(evidence_path.read_bytes())
            status["non_germany_evidence_ledger_published"]=True
            from ex_multileague_evidence_validation import validate as validate_evidence
            original_batches=json.loads(Path("ex_run/multileague_review_batches.json").read_text(encoding="utf-8"))
            evidence_validated=validate_evidence(evidence,original_batches)
            Path("reports/latest_multileague_evidence_validated_batch1.json").write_text(
                json.dumps(evidence_validated,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            status["non_germany_evidence_ledger_validated"]=True
        manifest_path=Path("ex_run/multileague_batch_manifest.json")
        if manifest_path.is_file():
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
            comparison=json.loads(Path("ex_run/multileague_shadow_comparison.json").read_text(encoding="utf-8"))
            if manifest.get("ex_final_allowed") is not False or manifest.get("independently_verified_added")!=0:
                raise ValueError("Unsafe batch manifest")
            if manifest.get("total_unmatched")!=comparison.get("shadow_unmatched"):
                raise ValueError("Batch manifest total mismatch")
            Path("reports/latest_multileague_batch_manifest.json").write_bytes(manifest_path.read_bytes())
            status["non_germany_batch_manifest_published"]=True
            from ex_multileague_manifest_validation import validate as validate_manifest
            source_batches=json.loads(Path("ex_run/multileague_review_batches.json").read_text(encoding="utf-8"))
            verified_manifest=validate_manifest(source_batches,manifest)
            Path("reports/latest_multileague_manifest_validated.json").write_text(
                json.dumps(verified_manifest,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            status["non_germany_batch_manifest_validated"]=True
        batches_path=Path("ex_run/multileague_review_batches.json")
        if batches_path.is_file():
            batches=json.loads(batches_path.read_text(encoding="utf-8"))
            comparison=json.loads(Path("ex_run/multileague_shadow_comparison.json").read_text(encoding="utf-8"))
            if batches.get("ex_final_allowed") is not False or batches.get("aliases_approved") is not False or batches.get("independently_verified_added")!=0:
                raise ValueError("Unsafe source review batches")
            if batches.get("total_unmatched")!=comparison.get("shadow_unmatched") or sum(b["count"] for b in batches["batches"])!=batches["total_unmatched"]:
                raise ValueError("Source review batches incomplete")
            Path("reports/latest_multileague_review_batches.json").write_bytes(batches_path.read_bytes())
            status["non_germany_review_batches_published"]=True
            from ex_multileague_batch_validation import validate as validate_batches
            source_summary=json.loads(Path("ex_other_shadow/review_summary.json").read_text(encoding="utf-8"))
            validated_batches=validate_batches(batches,source_summary)
            Path("reports/latest_multileague_batches_validated.json").write_text(
                json.dumps(validated_batches,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            status["non_germany_review_batches_validated"]=True
        priority_path=Path("ex_run/multileague_priority_plan.json")
        if priority_path.is_file():
            priority=json.loads(priority_path.read_text(encoding="utf-8"))
            comparison=json.loads(Path("ex_run/multileague_shadow_comparison.json").read_text(encoding="utf-8"))
            if priority.get("ex_final_allowed") is not False or priority.get("aliases_approved") is not False or priority.get("independently_verified_added")!=0:
                raise ValueError("Unsafe multi-league priority plan")
            if priority.get("total_unmatched")!=comparison.get("shadow_unmatched"):
                raise ValueError("Priority plan and shadow totals disagree")
            Path("reports/latest_multileague_priority_plan.json").write_bytes(priority_path.read_bytes())
            status["non_germany_priority_plan_published"]=True
        shadow_diagnostics_path=Path("ex_run/multileague_shadow_diagnostics.json")
        if shadow_diagnostics_path.is_file():
            shadow_diagnostics=json.loads(shadow_diagnostics_path.read_text(encoding="utf-8"))
            if shadow_diagnostics.get("ex_final_allowed") is not False or shadow_diagnostics.get("score_verified") is not False:
                raise ValueError("Unsafe post-shadow diagnostics")
            comparison=json.loads(Path("ex_run/multileague_shadow_comparison.json").read_text(encoding="utf-8"))
            if shadow_diagnostics.get("unmatched_total")!=comparison.get("shadow_unmatched"):
                raise ValueError("Post-shadow diagnostics mismatch")
            Path("reports/latest_multileague_shadow_diagnostics.json").write_bytes(shadow_diagnostics_path.read_bytes())
            status["non_germany_shadow_diagnostics_published"]=True
            from ex_multileague_shadow_validation import validate as validate_shadow
            validated_shadow=validate_shadow(comparison,shadow_diagnostics)
            Path("reports/latest_multileague_shadow_validated.json").write_text(
                json.dumps(validated_shadow,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            status["non_germany_shadow_validated"]=True
            from ex_multileague_priority_validation import validate as validate_priority
            priority=json.loads(Path("ex_run/multileague_priority_plan.json").read_text(encoding="utf-8"))
            validated_priority=validate_priority(priority,shadow_diagnostics,comparison)
            Path("reports/latest_multileague_priority_validated.json").write_text(
                json.dumps(validated_priority,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            status["non_germany_priority_validated"]=True
        shadow_queue_path=Path("ex_run/multileague_shadow_review_queue.json")
        if shadow_queue_path.is_file():
            shadow_queue=json.loads(shadow_queue_path.read_text(encoding="utf-8"))
            if shadow_queue.get("ex_final_allowed") is not False or shadow_queue.get("score_verified") is not False:
                raise ValueError("Unsafe post-shadow review queue")
            comparison=json.loads(Path("ex_run/multileague_shadow_comparison.json").read_text(encoding="utf-8"))
            if shadow_queue.get("total_review_queue")!=comparison.get("shadow_unmatched"):
                raise ValueError("Post-shadow review total differs from current comparison")
            Path("reports/latest_multileague_shadow_review_queue.json").write_bytes(shadow_queue_path.read_bytes())
            status["non_germany_shadow_review_queue_published"]=True
        other_shadow_path=Path("ex_run/multileague_shadow_comparison.json")
        if other_shadow_path.is_file():
            other_shadow=json.loads(other_shadow_path.read_text(encoding="utf-8"))
            if other_shadow.get("ex_final_allowed") is not False or other_shadow.get("independently_verified_added") != 0:
                raise ValueError("Unsafe other-league shadow")
            if other_shadow.get("baseline_unmatched") != status["unmatched_total"]-status["germany_unmatched"]:
                raise ValueError("Other-league baseline mismatch")
            Path("reports/latest_multileague_shadow_comparison.json").write_bytes(other_shadow_path.read_bytes())
            status["non_germany_shadow_unmatched"]=other_shadow["shadow_unmatched"]
        expanded_path=Path("ex_run/germany_expanded_shadow.json")
        if expanded_path.is_file():
            expanded=json.loads(expanded_path.read_text(encoding="utf-8"))
            if expanded.get("ex_final_allowed") is not False or expanded.get("independently_verified_added") != 0:
                raise ValueError("Unsafe expanded shadow evidence")
            Path("reports/latest_germany_expanded_shadow.json").write_bytes(expanded_path.read_bytes())
            status["germany_expanded_shadow_unmatched"]=expanded["expanded_shadow_unmatched"]
            from ex_germany_expanded_validation import validate
            base_count=status.get("germany_unmatched")
            first_data=json.loads(Path("ex_run/germany_shadow_comparison.json").read_text(encoding="utf-8"))
            candidate_reports=[
                json.loads(Path("ex_run/germany_alias_candidates.json").read_text(encoding="utf-8")),
                json.loads(Path("ex_run/germany_remaining_candidates.json").read_text(encoding="utf-8"))]
            validated=validate({"germany_unmatched":base_count},first_data,expanded,candidate_reports)
            Path("reports/latest_germany_expanded_validated.json").write_text(
                json.dumps(validated,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            status["germany_expanded_validated"]=True
        shadow_path=Path("ex_run/germany_shadow_comparison.json")
        if shadow_path.is_file():
            shadow=json.loads(shadow_path.read_text(encoding="utf-8"))
            if shadow.get("ex_final_allowed") is not False or shadow.get("aliases_approved") is not False:
                raise ValueError("Unsafe shadow evidence")
            Path("reports/latest_germany_shadow_comparison.json").write_bytes(shadow_path.read_bytes())
            status["germany_shadow_unmatched"]=shadow.get("shadow_germany_unmatched")
        candidate_path=Path("ex_run/germany_alias_candidates.json")
        if candidate_path.is_file():
            candidate_data=json.loads(candidate_path.read_text(encoding="utf-8"))
            if candidate_data.get("ex_final_allowed") is not False:
                raise ValueError("Unsafe alias candidate evidence")
            Path("reports/latest_germany_alias_candidates.json").write_bytes(candidate_path.read_bytes())
            status["germany_alias_candidates"]=len(candidate_data["candidates"])
        offline_path=Path("ex_run/germany_offline_shadow.json")
        shadow_path=Path("ex_run/germany_shadow_comparison.json")
        if offline_path.is_file() and shadow_path.is_file():
            from ex_germany_shadow_metrics import validate_shadow_metrics
            comparison=validate_shadow_metrics(
                {"germany_unmatched":status["germany_unmatched"]},
                json.loads(shadow_path.read_text(encoding="utf-8")),
                json.loads(offline_path.read_text(encoding="utf-8")))
            Path("reports/latest_germany_shadow_validated_metrics.json").write_text(
                json.dumps(comparison,ensure_ascii=False,indent=2)+chr(10),
                encoding="utf-8")
            status["germany_shadow_reduction"]=comparison["shadow_reduction"]
            status["independently_verified_added"]=0
    except (ValueError, KeyError, OSError) as exc:
        status["evidence_published"]=False
        status["publication_error"]=str(exc)
else:
    status["evidence_published"]=False
# Separate completed, scoped score reconciliations from the global source audit.
# These diagnostics are informational only and must never unlock EX FINAL.
status["audit_blockers"]=[]
if status.get("audit_status") != "READY":
    status["audit_blockers"].append("GLOBAL_SOURCE_AUDIT_NOT_READY")
if status.get("unmatched_total",0):
    status["audit_blockers"].append("BASELINE_SECONDARY_UNMATCHED")
if status.get("source_errors"):
    status["audit_blockers"].append("SECONDARY_SOURCE_ERRORS")
if not status.get("evidence_published"):
    status["audit_blockers"].append("EVIDENCE_PUBLICATION_INCOMPLETE")
status["strict_score_scope_is_global"]=False
status["germany_strict_score_scope_is_global"]=False
status["ex_final_allowed"]=False
Path("reports/latest_pipeline_status.json").write_text(
    json.dumps(status,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
print(json.dumps(status,ensure_ascii=False))
