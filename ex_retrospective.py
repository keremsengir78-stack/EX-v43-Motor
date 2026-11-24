"""Point-in-time reconstruction from settled events, with retrospective provenance."""

from collections import defaultdict
from datetime import timedelta
from statistics import mean

from ex_historical_features import market_labels
from ex_history_archive import utc
from ex_model_challengers import compare_calibration


EVIDENCE_CLASSES = {
    "retrospective_settled_events": ["score", "venue_form", "played_minutes", "kickoff_rest", "observed_load"],
    "requires_prematch_capture": ["lineup_availability", "injuries", "market_quote", "weather_forecast",
                                  "actual_travel_plan", "matchday_pitch_condition"],
}


def settled_facts(payload, event, retrieved_at):
    competition, = payload["header"]["competitions"]
    status = competition["status"]["type"]
    facts = {"event_id": event["event_id"], "competition": event["competition"],
             "season": event.get("source_season"), "teams": event["teams"],
             "kickoff": utc(event["kickoff_at"]), "score": None, "finished": None}
    if status.get("name") != "STATUS_FULL_TIME" or status.get("completed") is not True:
        return facts
    scores = {side["homeAway"]: str(side.get("score", "")) for side in competition["competitors"]}
    values = [scores[side] for side in ("home", "away")]
    if any(not v.isascii() or not v.isdigit() or int(v) > 30 for v in values):
        return facts
    facts["score"] = tuple(map(int, values))
    captured = utc(retrieved_at)
    if captured < facts["kickoff"] + timedelta(minutes=90):
        facts["score"] = None
        return facts
    ends = []
    for play in payload.get("keyEvents", []):
        if ((play.get("type") or {}).get("type") == "end-regular-time"
                and (play.get("period") or {}).get("number") == 2 and play.get("wallclock")):
            stamp = utc(play["wallclock"])
            if facts["kickoff"] + timedelta(minutes=90) <= stamp <= captured:
                ends.append(stamp)
    # Earliest certainty is the provider's terminal event or the completed capture.
    facts["terminal_source"] = "PROVIDER_END_REGULAR_TIME" if ends else "FINAL_STATUS_CAPTURE_UPPER_BOUND"
    facts["finished"] = max(ends) if ends else captured
    return facts


def window(games, values, side, season):
    venue = [game for game in games if game[1] == side]
    season_rows = [game for game in games if game[2]["season"] == season]
    previous = [game for game in venue if game[2]["season"] == season - 1]
    windows = venue[-5:], venue[-10:], season_rows, previous
    if len(windows[0]) < 5:
        return None, None
    short = {market: mean(values[game[2]["event_id"]][market] if game[1] == side else
                          values[game[2]["event_id"]][{"MS1": "MS2", "MS2": "MS1"}.get(market, market)]
                          for game in windows[0]) for market in values[venue[-1][2]["event_id"]]}
    if len(windows[1]) < 10 or not season_rows or not previous:
        return short, None
    weighted = {}
    for market in short:
        opposite = {"MS1": "MS2", "MS2": "MS1"}.get(market, market)
        weighted[market] = sum(weight * mean(values[game[2]["event_id"]][market if game[1] == side else opposite]
                                             for game in rows)
                               for weight, rows in zip((.4, .3, .2, .1), windows, strict=True))
    return short, weighted


def workload(games, kickoff):
    recent = [row for row in games if kickoff - row["kickoff"] <= timedelta(days=14)]
    if not recent:
        return None, None
    rest = min((kickoff - max(row["kickoff"] for row in recent)).total_seconds() / 3600, 336)
    vectors = (rest / 336, len(recent) / 5)
    minutes = [row.get("minutes", {}).get(row["index_team"]) for row in recent]
    return vectors, (sum(minutes) / 990 / 5,) if all(m is not None for m in minutes) else None


def build_examples(events):
    targets = sorted((row for row in events if row["score"] is not None), key=lambda r: r["kickoff"])
    settled = sorted((row for row in targets if row["finished"]), key=lambda r: r["finished"])
    labels = {row["event_id"]: market_labels(*row["score"]) for row in targets}
    competition_history, all_history = defaultdict(list), defaultdict(list)
    examples, cursor = [], 0
    for target in targets:
        kickoff = target["kickoff"]
        while cursor < len(settled) and settled[cursor]["finished"] < kickoff:
            previous = settled[cursor]
            for side, team in previous["teams"].items():
                competition_history[previous["competition"], team].append((previous["kickoff"], side, previous))
                all_history[team].append({**previous, "index_team": team})
            cursor += 1
        if type(target["season"]) is not int:
            continue
        sides = []
        for side, team in target["teams"].items():
            league_history = sorted(competition_history[target["competition"], team], key=lambda row: row[0])
            sides.append((window(league_history, labels, side, target["season"]), workload(all_history[team], kickoff)))
        ((hs, hw), (hc, hm)), ((aws, aw), (ac, am)) = sides
        if not hs or not aws:
            continue
        examples.append({
            "event_id": target["event_id"], "kickoff": kickoff, "finished": target["finished"],
            "labels": labels[target["event_id"]], "short": {m: mean((hs[m], aws[m])) for m in hs},
            "strength": {m: mean((hw[m], aw[m])) for m in hs} if hw and aw else None,
            "workload": (*hc, *ac) if hc and ac else None, "minutes": (*hm, *am) if hm and am else None,
        })
    return examples


def evaluate(examples):
    report = {}
    for market in ("MS1", "MS2", "KG_VAR", "2.5_UST"):
        # Keep target labels settled on their UTC date for strictly separated day partitions.
        def cohort(baseline, context=None):
            return [(r["kickoff"].date(), r[baseline][market], r["labels"][market],
                     r[context] if context else ())
                    for r in examples if r[baseline] and (not context or r[context] is not None)
                    and r["finished"] and r["finished"].date() == r["kickoff"].date()]

        report[market] = {}
        for name, baseline, context in (("venue5_reference", "short", None),
                                        ("fixed_weight_strength", "strength", None),
                                        ("conditions_rest_load", "strength", "workload"),
                                        ("conditions_minutes", "strength", "minutes")):
            rows = cohort(baseline, context)
            report[market][name] = {"retrospective_n": len(rows), **compare_calibration(rows)}
        weighted = [r for r in examples if r["strength"] and r["finished"]
                    and r["finished"].date() == r["kickoff"].date()]
        from ex_model_challengers import date_partitions
        from ex_component_experiment import weekly_interval
        partitions = date_partitions([(r["kickoff"].date(), r) for r in weighted])
        if partitions:
            test = partitions[-1]
            observed = [r["labels"][market] for _, r in test]
            old = [(r["short"][market] - y)**2 for (_, r), y in zip(test, observed, strict=True)]
            new = [(r["strength"][market] - y)**2 for (_, r), y in zip(test, observed, strict=True)]
            report[market]["fixed_weights_vs_venue5"] = {
                "test_n": len(test), "venue5_brier": mean(old), "weighted_brier": mean(new),
                "weekly_delta_brier_99pct": weekly_interval(test, old, new),
            }
        report[market]["external_factors"] = {"status": "UNAVAILABLE_PREMATCH_EVIDENCE"}
    return report
