"""
Josh Talks Transcription Quality Analysis - Core Metrics & Preprocessing.

Provides deterministic mathematical calculations for:
- Task-to-Audio Time Ratio (TER)
- Clean Character Counting (excluding whitespace and '[blank]')
- Characters Per Second (CPS) throughput
- Empirical threshold derivation matching original baseline distributions
"""

from typing import Dict
import numpy as np
import pandas as pd


def calculate_ter(task_time: pd.Series, duration: pd.Series) -> pd.Series:
    """
    Calculate the Task-to-Audio Ratio (TER):
        TER = time_taken_by_user / audio_duration

    A TER < 1.0 implies the transcriber spent less time on the task than
    the real-time playback duration of the audio clip.
    """
    time_clean = pd.to_numeric(task_time, errors="coerce")
    dur_clean = pd.to_numeric(duration, errors="coerce")

    # Division with pandas series handles division by zero as inf
    ter = time_clean / dur_clean
    return ter


def clean_text_series(series: pd.Series) -> pd.Series:
    """Normalize text by converting NaN to empty string, casting to str, and stripping edges."""
    return series.fillna("").astype(str).str.strip()


def count_non_space_characters(text_series: pd.Series) -> pd.Series:
    """
    Count non-whitespace characters in transcription text.
    Explicitly ignores literal '[blank]' tokens (case-insensitive).
    """
    cleaned = clean_text_series(text_series)
    effective_text = cleaned.where(cleaned.str.lower().ne("[blank]"), "")
    return effective_text.str.replace(r"\s+", "", regex=True).str.len()


def calculate_cps(char_count: pd.Series, task_time: pd.Series) -> pd.Series:
    """
    Calculate transcription speed in Characters Per Second (CPS):
        CPS = character_count / task_time_taken

    Only computed for tasks where task_time > 0. Returns NaN otherwise.
    """
    time_clean = pd.to_numeric(task_time, errors="coerce")
    chars_clean = pd.to_numeric(char_count, errors="coerce")

    valid_time = time_clean.where(time_clean > 0)
    return chars_clean / valid_time


def derive_empirical_thresholds(
    df: pd.DataFrame,
    ter_quantile: float = 0.01,
    cps_quantile: float = 0.98,
) -> Dict[str, float]:
    """
    Derive data-driven thresholds from the actual empirical distributions:
    - TER threshold: bottom 1st percentile of valid, finite TER values (0.1788)
    - CPS threshold: top 98th percentile of CPS values for clips with duration > 5s (59.8576)
    """
    ter_valid = df["ter"].replace([np.inf, -np.inf], np.nan).dropna()
    ter_p1 = float(ter_valid.quantile(ter_quantile))

    cps_population = df.loc[
        df["is_duration_above_5s"] & df["user_task_cps"].notna(),
        "user_task_cps",
    ]
    cps_p98 = float(cps_population.quantile(cps_quantile))

    return {
        "ter_p1": ter_p1,
        "cps_p98": cps_p98,
        "ter_quantile": ter_quantile,
        "cps_quantile": cps_quantile,
    }
