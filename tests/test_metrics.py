"""
Unit tests for src/metrics.py.
Tests calculation functions for TER, CPS, character counting, and threshold derivation.
"""

import unittest
import numpy as np
import pandas as pd

from src.metrics import (
    calculate_ter,
    clean_text_series,
    count_non_space_characters,
    calculate_cps,
    derive_empirical_thresholds,
)


class TestMetrics(unittest.TestCase):
    def test_calculate_ter_standard(self):
        task_time = pd.Series([10.0, 5.0, 20.0])
        duration = pd.Series([10.0, 10.0, 10.0])
        ter = calculate_ter(task_time, duration)
        expected = [1.0, 0.5, 2.0]
        np.testing.assert_allclose(ter.values, expected)

    def test_calculate_ter_edge_cases(self):
        task_time = pd.Series([5.0, np.nan, "10.0", 0.0])
        duration = pd.Series([0.0, 10.0, "5.0", 5.0])
        ter = calculate_ter(task_time, duration)

        # 5.0 / 0.0 -> inf
        self.assertTrue(np.isinf(ter.iloc[0]))
        # nan / 10.0 -> nan
        self.assertTrue(np.isnan(ter.iloc[1]))
        # "10.0" / "5.0" -> 2.0
        self.assertAlmostEqual(ter.iloc[2], 2.0)
        # 0.0 / 5.0 -> 0.0
        self.assertAlmostEqual(ter.iloc[3], 0.0)

    def test_clean_text_series(self):
        series = pd.Series(["  hello world  ", None, np.nan, "text\n", 123])
        cleaned = clean_text_series(series)
        self.assertEqual(cleaned.iloc[0], "hello world")
        self.assertEqual(cleaned.iloc[1], "")
        self.assertEqual(cleaned.iloc[2], "")
        self.assertEqual(cleaned.iloc[3], "text")
        self.assertEqual(cleaned.iloc[4], "123")

    def test_count_non_space_characters(self):
        series = pd.Series([
            "hello world",        # 10 non-space chars
            "  h e l l o  ",      # 5 chars
            "[blank]",            # Literal blank token -> 0 chars
            "[BLANK]",            # Case-insensitive blank -> 0 chars
            "",                   # Empty -> 0
            "नमस्ते भारत",        # Unicode Hindi chars -> 11 non-space chars
        ])
        counts = count_non_space_characters(series)
        self.assertEqual(counts.iloc[0], 10)
        self.assertEqual(counts.iloc[1], 5)
        self.assertEqual(counts.iloc[2], 0)
        self.assertEqual(counts.iloc[3], 0)
        self.assertEqual(counts.iloc[4], 0)
        self.assertEqual(counts.iloc[5], 10)

    def test_calculate_cps(self):
        chars = pd.Series([100, 50, 0, 100])
        task_time = pd.Series([10.0, 0.0, 5.0, np.nan])
        cps = calculate_cps(chars, task_time)

        self.assertAlmostEqual(cps.iloc[0], 10.0)
        # task_time <= 0 must be NaN to prevent division by zero anomaly
        self.assertTrue(np.isnan(cps.iloc[1]))
        self.assertAlmostEqual(cps.iloc[2], 0.0)
        self.assertTrue(np.isnan(cps.iloc[3]))

    def test_derive_empirical_thresholds(self):
        # Create a synthetic dataset with known quantiles
        df = pd.DataFrame({
            "ter": np.linspace(0.1, 10.0, 100),
            "user_task_cps": np.linspace(1.0, 100.0, 100),
            "duration_clean": [10.0] * 100,
            "is_duration_above_5s": [True] * 100,
        })
        thresholds = derive_empirical_thresholds(df, ter_quantile=0.05, cps_quantile=0.95)
        self.assertIn("ter_p1", thresholds)
        self.assertIn("cps_p98", thresholds)
        self.assertAlmostEqual(thresholds["ter_p1"], float(df["ter"].quantile(0.05)))
        self.assertAlmostEqual(thresholds["cps_p98"], float(df["user_task_cps"].quantile(0.95)))


if __name__ == "__main__":
    unittest.main()
