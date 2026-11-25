import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ex_decision import MARKETS
from ex_history_archive import utc
from ex_research_components import archive_weather, metrics, score_components, weather_vector


class ResearchComponentTests(unittest.TestCase):
    def test_research_scores_use_fixed_weights_without_opening_production(self):
        as_of = utc("2026-11-25T13:00:00Z")
        model = {
            "components": {key: {"latest_training_finish": "2026-11-24T23:00:00Z"}
                           for key in ("match_conditions", "external_factors")},
            "coefficients": {
                "match_conditions": {market: [0, 0, 0, 0, 0] for market in MARKETS},
                "external_factors": {market: [0, 0, 0, 0] for market in MARKETS},
            },
        }
        strength = dict.fromkeys(MARKETS, .8)
        scores, decisions = score_components(strength, (0, 0, 0, 0), (0, 0, 0), model, as_of)
        self.assertAlmostEqual(.65, scores["MS1"]["weighted_research_score"])
        self.assertIsNone(decisions["markets"]["MS1"]["ex_g"]["probability"])
        self.assertFalse(decisions["ex_final_allowed"])
        scores, _ = score_components(strength, (0, 0, 0, 0), None, model, as_of)
        self.assertIsNone(scores["MS1"]["weighted_research_score"])
        scores, _ = score_components(strength, (0, 0, 0, 0), None, model,
                                     utc("2026-11-24T22:00:00Z"))
        self.assertIsNone(scores["MS1"]["components"]["match_conditions"]["score"])

    def test_weather_requires_expected_hour_and_prematch_timestamp(self):
        item = {"kind": "PREMATCH_NUMERICAL_FORECAST", "forecast_hour_utc": "2026-11-25T20:00:00Z",
                "source": {"retrieved_at": "2026-11-25T13:00:00Z", "sha256": "a" * 64,
                           "url": "https://api.open-meteo.com/v1/forecast?timezone=GMT"},
                "values": {"temperature_2m": 15, "precipitation_probability": 25, "wind_speed_10m": 10}}
        self.assertEqual((.5, .25, .2), weather_vector(item, "2026-11-25T20:30:00Z",
                                                     utc("2026-11-25T13:01:00Z")))
        self.assertIsNone(weather_vector(item, "2026-11-25T20:30:00Z", utc("2026-11-25T13:00:00Z")))
        self.assertIsNone(weather_vector(item, "2026-11-25T21:30:00Z", utc("2026-11-25T13:01:00Z")))

        item["source"]["sha256"] = "missing"
        self.assertIsNone(weather_vector(item, "2026-11-25T20:30:00Z", utc("2026-11-25T13:01:00Z")))

    def test_archive_weather_rejects_packs_sealed_after_kickoff(self):
        source = {"url": "https://api.open-meteo.com/v1/forecast?timezone=GMT",
                  "sha256": "a" * 64, "retrieved_at": "2026-11-25T12:00:00Z"}
        item = {"kind": "PREMATCH_NUMERICAL_FORECAST", "source": source,
                "forecast_hour_utc": "2026-11-25T20:00:00Z",
                "values": {"temperature_2m": 10, "precipitation_probability": 0, "wind_speed_10m": 5}}
        kickoff = "2026-11-25T20:00:00Z"
        row = {"fixture": {"event_id": "fixture", "kickoff_at": kickoff}, "as_of": "2026-11-25T13:00:00Z",
               "observed_inputs": {"prematch_weather_forecast": item}}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            forecasts = root / "1" / "forecasts"
            forecasts.mkdir(parents=True)
            (forecasts / "daily-analysis.json").write_text(json.dumps([row]))
            receipt = forecasts.parent / "receipt.json"
            cutoff = utc("2026-11-26T00:00:00Z")
            receipt.write_text(json.dumps({"created_at": kickoff}))
            self.assertEqual({}, archive_weather(root, cutoff))
            receipt.write_text(json.dumps({"created_at": "2026-11-25T14:00:00Z"}))
            self.assertEqual({("fixture", utc(kickoff)): item}, archive_weather(root, cutoff))

    def test_metrics_keep_brier_and_calibration_separate(self):
        report, _ = metrics([{"label": 1}, {"label": 0}], [.5, .5])
        self.assertEqual(.25, report["brier"])
        self.assertEqual(0., report["ece_10_equal_width"])
