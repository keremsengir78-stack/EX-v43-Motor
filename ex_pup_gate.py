"""Check the registered four-market boundary before PUP."""

import math


def gate_pup(markets, expected):
    issues = []
    for market in expected:
        record = markets.get(market, {}).get("ex_g", {})
        chance = record.get("probability")
        if (record.get("status") != "EX_G_AVAILABLE" or record.get("market") != market
                or type(chance) not in (int, float) or not math.isfinite(chance) or not 0 <= chance <= 1):
            issues.append(f"{market}:calibrated_probability_missing")
    # The registered engine has no executable user-approved PUP protocol.
    issues.append("pup:approved_executor_unavailable")
    return {"status": "BLOCKED", "issues": issues, "markets_checked": list(expected),
            "pup_allowed": False, "ex_final_allowed": False}
