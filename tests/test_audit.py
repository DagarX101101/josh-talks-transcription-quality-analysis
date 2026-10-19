"""
Unit tests for src/audit.py.
Tests dataset preprocessing, warning signals flagging, overlap matrix,
transcriber aggregation, and governance candidacy classification.
"""

import unittest
import numpy as np
import pandas as pd

from src.audit import (
    preprocess_dataset,
    flag_task_warnings,
    compute_signal_overlap,
    aggregate_transcriber_risk,
    identify_passthrough_cohort,
    identify_block_candidates,
)


class TestAudit(unittest.TestCase):
    def setUp(self):
        # Construct controlled synthetic dataset
        self.raw_data = pd.DataFrame({
            "user_id": [101, 101, 101, 102, 103],
            "recording_url": [f"http://audio/{i}.mp3" for i in range(5)],
            "whisper_text": [
                "valid audio whisper transcription",
                "another whisper transcription",
                "third clip transcription",
                "whisper clip 4",
                "",  # empty whisper
            ],
            "user_text": [
                "[blank]",                           # Flag 1: blank submission with whisper
                "another whisper transcription",     # Exact pass-through
                "a third clip user edit",            # Standard submission
                "",                                  # Flag 1: empty submission with whisper
                "",                                  # Not flag 1: whisper was empty
            ],
            "is_edited": ["No", "No", "Yes", "No", "No"],
            "duration": [10.0, 10.0, 10.0, 10.0, 0.5],
            "time_taken_by_user": [2.0, 0.5, 25.0, 0.2, 0.1],
            "segment_character_per_second": [0.0, 60.0, 5.0, 0.0, 0.0],
        })

    def test_preprocess_dataset(self):
        df_clean = preprocess_dataset(self.raw_data)
        self.assertIn("ter", df_clean.columns)
        self.assertIn("analysis_char_count", df_clean.columns)
        self.assertIn("user_task_cps", df_clean.columns)
        self.assertIn("is_duration_above_1s", df_clean.columns)

        # Check TER values
        self.assertAlmostEqual(df_clean.loc[0, "ter"], 0.2)
        self.assertAlmostEqual(df_clean.loc[1, "ter"], 0.05)
        self.assertAlmostEqual(df_clean.loc[2, "ter"], 2.5)

        # Check character count for [blank] is 0
        self.assertEqual(df_clean.loc[0, "analysis_char_count"], 0)

    def test_flag_task_warnings(self):
        df_clean = preprocess_dataset(self.raw_data)
        thresholds = {
            "ter_p1": 0.10,
            "cps_p98": 50.0,
        }
        df_flagged, thresh_out = flag_task_warnings(df_clean, thresholds)

        # Task 0: [blank] with whisper & duration > 1s -> blank flag True
        self.assertTrue(df_flagged.loc[0, "flag_blank_submission"])
        # Task 1: TER = 0.05 < 0.10 -> extreme low ter True
        self.assertTrue(df_flagged.loc[1, "flag_extreme_low_ter"])
        # Task 1: TER = 0.05 < 1.0 -> ter_below_1 True
        self.assertTrue(df_flagged.loc[1, "flag_ter_below_1"])
        # Task 2: TER = 2.5 > 1.0 -> ter_below_1 False
        self.assertFalse(df_flagged.loc[2, "flag_ter_below_1"])
        # Task 4: duration = 0.5 (< 1.0) -> flags must be False
        self.assertFalse(df_flagged.loc[4, "flag_blank_submission"])
        self.assertFalse(df_flagged.loc[4, "flag_extreme_low_ter"])

        self.assertIn("any_warning", df_flagged.columns)

    def test_compute_signal_overlap(self):
        df_clean = preprocess_dataset(self.raw_data)
        thresholds = {"ter_p1": 0.10, "cps_p98": 50.0}
        df_flagged, _ = flag_task_warnings(df_clean, thresholds)
        warning_cols = [
            "flag_blank_submission",
            "flag_extreme_low_ter",
            "flag_ter_below_1",
            "flag_extreme_cps",
        ]
        matrix = compute_signal_overlap(df_flagged, warning_cols)
        self.assertEqual(matrix.shape, (4, 4))
        # Diagonal elements must equal total counts of individual flags
        for col in warning_cols:
            self.assertEqual(matrix.loc[col, col], df_flagged[col].sum())

    def test_aggregate_transcriber_risk(self):
        df_clean = preprocess_dataset(self.raw_data)
        thresholds = {"ter_p1": 0.10, "cps_p98": 50.0}
        df_flagged, _ = flag_task_warnings(df_clean, thresholds)
        warning_cols = [
            "flag_blank_submission",
            "flag_extreme_low_ter",
            "flag_ter_below_1",
            "flag_extreme_cps",
        ]
        user_summary, repeat_users = aggregate_transcriber_risk(df_flagged, warning_cols)

        # User 101 has 3 tasks, user 102 has 1 task, user 103 has 1 task
        self.assertEqual(len(user_summary), 3)
        self.assertEqual(len(repeat_users), 1)
        self.assertEqual(repeat_users.iloc[0]["user_id"], 101)
        self.assertEqual(repeat_users.iloc[0]["total_tasks"], 3)

    def test_identify_passthrough_cohort(self):
        df_clean = preprocess_dataset(self.raw_data)
        thresholds = {"ter_p1": 0.10, "cps_p98": 50.0}
        df_flagged, _ = flag_task_warnings(df_clean, thresholds)
        cohort = identify_passthrough_cohort(df_flagged)

        # Task 1 has extreme TER (0.05 < 0.10), high CPS (27 chars / 0.5s = 54 > 50), unchanged whisper
        self.assertEqual(len(cohort), 1)
        self.assertEqual(cohort.index[0], 1)


if __name__ == "__main__":
    unittest.main()
