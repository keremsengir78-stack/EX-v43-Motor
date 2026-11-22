import unittest
import io
import json
from unittest.mock import patch
from ex_espn_provider import parse_espn_scoreboard, fetch_espn_scoreboard, MAX_SCOREBOARD_BYTES


def event(home=2, away=1):
    return {"date": "2026-01-01T12:00:00Z",
            "status": {"type": {"completed": True}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"displayName": "Home"}, "score": home},
                {"homeAway": "away", "team": {"displayName": "Away"}, "score": away}
            ]}]}


def parse(events):
    return parse_espn_scoreboard({"events": events}, "en.1", "2026-02-01")


class ESPNFetchTests(unittest.TestCase):
    def _fetch(self, events, day="2026-01-01", as_of="2026-02-01"):
        raw = json.dumps({"events": events}).encode("utf-8")
        with patch("ex_espn_provider.urllib.request.urlopen", return_value=io.BytesIO(raw)) as request:
            rows, provenance = fetch_espn_scoreboard("en.1", day, as_of)
        return rows, provenance, request

    def test_fetch_oversized_response_rejected(self):
        with patch("ex_espn_provider.urllib.request.urlopen",
                   return_value=io.BytesIO(b"x" * (MAX_SCOREBOARD_BYTES + 1))):
            with self.assertRaisesRegex(ValueError, "size limit"):
                fetch_espn_scoreboard("en.1", "2026-01-01", "2026-02-01")

    def test_fetch_exact_limit_does_not_raise_size_error(self):
        raw = b" " * MAX_SCOREBOARD_BYTES
        with patch("ex_espn_provider.urllib.request.urlopen", return_value=io.BytesIO(raw)):
            with self.assertRaises(json.JSONDecodeError):
                fetch_espn_scoreboard("en.1", "2026-01-01", "2026-02-01")

    def test_fetch_read_uses_bounded_size(self):
        class RecordingStream(io.BytesIO):
            requested = None
            def read(self, size=-1):
                self.requested = size
                return super().read(size)
        stream = RecordingStream(json.dumps({"events": [event()]}).encode())
        with patch("ex_espn_provider.urllib.request.urlopen", return_value=stream):
            fetch_espn_scoreboard("en.1", "2026-01-01", "2026-02-01")
        self.assertEqual(stream.requested, MAX_SCOREBOARD_BYTES + 1)

    def test_fetch_small_valid_response_still_works(self):
        rows, provenance, _ = self._fetch([event()])
        self.assertEqual(len(rows), 1)
        self.assertGreater(provenance["raw_bytes"], 0)

    def test_fetch_empty_response_does_not_certify(self):
        with patch("ex_espn_provider.urllib.request.urlopen", return_value=io.BytesIO(b"")):
            with self.assertRaises(json.JSONDecodeError):
                fetch_espn_scoreboard("en.1", "2026-01-01", "2026-02-01")

    def test_fetch_accepts_matching_historical_event(self):
        rows, provenance, _ = self._fetch([event()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(provenance["provider"], "ESPN")

    def test_fetch_rejects_other_day_in_provider_response(self):
        other = event()
        other["date"] = "2026-01-02T12:00:00Z"
        rows, _, _ = self._fetch([other])
        self.assertEqual(rows, [])

    def test_fetch_keeps_only_requested_day_in_mixed_response(self):
        other = event()
        other["date"] = "2026-01-02T12:00:00Z"
        rows, _, _ = self._fetch([event(), other])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-01-01")

    def test_fetch_provenance_hash_matches_raw_bytes(self):
        import hashlib
        raw = json.dumps({"events": [event()]}).encode("utf-8")
        rows, provenance, _ = self._fetch([event()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(provenance["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(provenance["raw_bytes"], len(raw))

    def test_fetch_rejects_cutoff_day_before_network_request(self):
        with patch("ex_espn_provider.urllib.request.urlopen") as request:
            with self.assertRaises(ValueError):
                fetch_espn_scoreboard("en.1", "2026-02-01", "2026-02-01")
            request.assert_not_called()


class ESPNMalformedTests(unittest.TestCase):
    def test_date_prefix_with_garbage_suffix_rejected(self):
        bad = event()
        bad["date"] = "2026-01-01garbage"
        self.assertEqual(parse([bad]), [])

    def test_date_only_without_timezone_rejected(self):
        bad = event()
        bad["date"] = "2026-01-01"
        self.assertEqual(parse([bad]), [])

    def test_naive_timestamp_rejected(self):
        bad = event()
        bad["date"] = "2026-01-01T12:00:00"
        self.assertEqual(parse([bad]), [])

    def test_non_utc_offset_timestamp_rejected(self):
        bad = event()
        bad["date"] = "2026-01-01T15:00:00+03:00"
        self.assertEqual(parse([bad]), [])

    def test_valid_utc_timestamp_accepted(self):
        self.assertEqual(len(parse([event()])), 1)

    def test_blank_home_team_skipped(self):
        bad = event()
        bad["competitions"][0]["competitors"][0]["team"]["displayName"] = " "
        self.assertEqual(parse([bad]), [])

    def test_blank_away_team_skipped(self):
        bad = event()
        bad["competitions"][0]["competitors"][1]["team"]["displayName"] = ""
        self.assertEqual(parse([bad]), [])

    def test_arabic_indic_digits_rejected(self):
        self.assertEqual(parse([event("٢", "١")]), [])

    def test_fullwidth_digits_rejected(self):
        self.assertEqual(parse([event("２", "１")]), [])

    def test_ascii_digits_still_accepted(self):
        result = parse([event("2", "1")])
        self.assertEqual(len(result), 1)

    def test_null_event_date_skipped(self):
        bad = event()
        bad["date"] = None
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_numeric_event_date_skipped(self):
        bad = event()
        bad["date"] = 20260101
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_short_event_date_skipped(self):
        bad = event()
        bad["date"] = "2026"
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_same_team_fixture_skipped(self):
        bad = event()
        bad["competitions"][0]["competitors"][1]["team"]["displayName"] = "HOME"
        self.assertEqual(parse([bad]), [])

    def test_valid_fixture_remains_accepted(self):
        self.assertEqual(len(parse([event()])), 1)

    def test_requested_day_filters_other_dates(self):
        first, second = event(), event()
        second["date"] = "2026-01-02T12:00:00Z"
        result = parse_espn_scoreboard({"events": [first, second]}, "en.1",
                                       "2026-02-01", requested_day="2026-01-01")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2026-01-01")

    def test_requested_day_accepts_matching_date(self):
        result = parse_espn_scoreboard({"events": [event()]}, "en.1",
                                       "2026-02-01", requested_day="2026-01-01")
        self.assertEqual(len(result), 1)

    def test_requested_day_at_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            parse_espn_scoreboard({"events": [event()]}, "en.1",
                                  "2026-02-01", requested_day="2026-02-01")

    def test_invalid_requested_day_rejected(self):
        with self.assertRaises(ValueError):
            parse_espn_scoreboard({"events": [event()]}, "en.1",
                                  "2026-02-01", requested_day="invalid")

    def test_no_requested_day_preserves_legacy_parser(self):
        first, second = event(), event()
        second["date"] = "2026-01-02T12:00:00Z"
        self.assertEqual(len(parse([first, second])), 2)

    def test_identical_duplicate_match_deduplicated(self):
        self.assertEqual(len(parse([event(), event()])), 1)

    def test_conflicting_duplicate_match_blocks(self):
        with self.assertRaisesRegex(ValueError, "conflicting ESPN scores"):
            parse([event(2, 1), event(3, 1)])

    def test_duplicate_team_case_variants_deduplicated(self):
        first, second = event(), event()
        second["competitions"][0]["competitors"][0]["team"]["displayName"] = "HOME"
        self.assertEqual(len(parse([first, second])), 1)

    def test_malformed_date_does_not_crash_other_results(self):
        bad = event()
        bad["date"] = "invalid"
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_different_match_scores_are_independent(self):
        first, second = event(), event(3, 0)
        second["competitions"][0]["competitors"][0]["team"]["displayName"] = "Other"
        self.assertEqual(len(parse([first, second])), 2)

    def test_non_dict_event_skipped(self):
        self.assertEqual(len(parse([None, event()])), 1)

    def test_non_list_competitions_skipped(self):
        bad = event()
        bad["competitions"] = None
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_missing_status_skipped(self):
        bad = event()
        bad["status"] = None
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_boolean_score_rejected(self):
        self.assertEqual(parse([event(True, 1)]), [])

    def test_non_numeric_score_rejected(self):
        self.assertEqual(parse([event("2.0", 1)]), [])

    def test_valid_numeric_string_score_accepted(self):
        result = parse([event("2", "1")])
        self.assertEqual((result[0]["home_goals"], result[0]["away_goals"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
