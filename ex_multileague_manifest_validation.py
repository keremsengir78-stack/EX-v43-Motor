"""Recompute source-review batch hashes and reject altered manifests."""
from ex_multileague_batch_manifest import manifest


def validate(batches, supplied):
    expected=manifest(batches)
    if supplied != expected:
        raise ValueError("source-review manifest content or hash mismatch")
    if supplied.get("ex_final_allowed") is not False or supplied.get("independently_verified_added")!=0:
        raise ValueError("unsafe manifest state")
    return {"total_unmatched":expected["total_unmatched"],
            "batch_count":expected["batch_count"],
            "hashes_verified":len(expected["batches"]),
            "independently_verified_added":0,
            "ex_final_allowed":False}
