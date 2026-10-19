"""
Josh Talks Transcription Quality Analysis - Audit & Governance Engine.

Implements task-level warning signals, signal overlap analysis, transcriber-level
aggregation, zero-review pass-through isolation, and policy candidate classification.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from src.metrics import (
    calculate_ter,
    clean_text_series,
    count_non_space_characters,
    calculate_cps,
    derive_empirical_thresholds,
)


def preprocess_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer prerequisite columns without mutating the raw dataframe."""
    clean_df = df.copy()

    # 1. Clean numeric duration and user time
    clean_df["duration_clean"] = pd.to_numeric(clean_df["duration"], errors="coerce")
    clean_df["task_time_clean"] = pd.to_numeric(
        clean_df["time_taken_by_user"], errors="coerce"
    )

    # 2. Time-to-Audio Ratio (TER)
    clean_df["ter"] = calculate_ter(
        clean_df["task_time_clean"], clean_df["duration_clean"]
    )

    # 3. Text cleaning & normalization
    user_text_clean = clean_text_series(clean_df["user_text"])
    whisper_text_clean = clean_text_series(clean_df["whisper_text"])

    clean_df["is_empty_submission"] = user_text_clean.eq("")
    clean_df["is_blank_only_submission"] = user_text_clean.eq("[blank]")
    clean_df["is_whisper_available"] = whisper_text_clean.ne("")
    clean_df["is_transcript_unchanged"] = user_text_clean.eq(whisper_text_clean)

    # 4. Character count and Characters Per Second (CPS)
    clean_df["analysis_char_count"] = count_non_space_characters(user_text_clean)
    clean_df["user_task_cps"] = calculate_cps(
        clean_df["analysis_char_count"], clean_df["task_time_clean"]
    )

    # 5. Audio duration eligibility masks
    clean_df["is_duration_above_1s"] = clean_df["duration_clean"].gt(1.0)
    clean_df["is_duration_above_5s"] = clean_df["duration_clean"].gt(5.0)

    return clean_df


def flag_task_warnings(
    df: pd.DataFrame,
    thresholds: Dict[str, float] = None,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Apply task-level warning flags based on empirical distribution thresholds.

    Signals:
    1. flag_blank_submission: Empty or '[blank]' submission when Whisper audio text is present (duration > 1s)
    2. flag_extreme_low_ter: Task time is in the bottom 1% of audio playback ratio (TER < 0.1788)
    3. flag_ter_below_1: Task time was shorter than audio duration (TER < 1.0)
    4. flag_extreme_cps: Character throughput in top 2% of population (> 59.8576 chars/sec for duration > 5s)
    """
    flagged = df.copy()

    if thresholds is None:
        thresholds = derive_empirical_thresholds(flagged)

    ter_p1 = thresholds["ter_p1"]
    cps_p98 = thresholds["cps_p98"]

    # Signal 1: Blank / incomplete submission despite audio content
    flagged["flag_blank_submission"] = (
        (flagged["is_empty_submission"] | flagged["is_blank_only_submission"])
        & flagged["is_whisper_available"]
        & flagged["is_duration_above_1s"]
    )

    # Signal 2: Extreme low TER (bottom 1% empirical boundary)
    flagged["flag_extreme_low_ter"] = (
        flagged["ter"].lt(ter_p1)
        & flagged["ter"].notna()
        & flagged["is_duration_above_1s"]
    )

    # Signal 3: TER below 1 (impossible full listening speed)
    flagged["flag_ter_below_1"] = (
        flagged["ter"].lt(1.0)
        & flagged["ter"].notna()
        & flagged["is_duration_above_1s"]
    )

    # Signal 4: Extreme CPS throughput (top 2% empirical boundary)
    flagged["flag_extreme_cps"] = (
        flagged["is_duration_above_5s"]
        & flagged["user_task_cps"].gt(cps_p98)
        & flagged["is_duration_above_1s"]
    )

    warning_cols = [
        "flag_blank_submission",
        "flag_extreme_low_ter",
        "flag_ter_below_1",
        "flag_extreme_cps",
    ]
    flagged["any_warning"] = flagged[warning_cols].any(axis=1)

    thresholds_out = {
        "ter_p1": ter_p1,
        "cps_p98": cps_p98,
        "warning_cols": warning_cols,
    }
    return flagged, thresholds_out


def compute_signal_overlap(df: pd.DataFrame, warning_cols: List[str]) -> pd.DataFrame:
    """Compute co-occurrence matrix between warning flags."""
    matrix = df[warning_cols].astype(int).T.dot(df[warning_cols].astype(int))
    return matrix


def aggregate_transcriber_risk(
    df: pd.DataFrame, warning_cols: List[str]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aggregate warning flag counts and rates by user_id.
    Isolates repeat transcribers (> 1 task) from single-task contributors.
    """
    user_summary = (
        df.groupby("user_id")
        .agg(
            total_tasks=("recording_url", "count"),
            blank_tasks=("flag_blank_submission", "sum"),
            extreme_low_ter_tasks=("flag_extreme_low_ter", "sum"),
            ter_below_1_tasks=("flag_ter_below_1", "sum"),
            extreme_cps_tasks=("flag_extreme_cps", "sum"),
            flagged_tasks=("any_warning", "sum"),
        )
        .reset_index()
    )

    user_summary["warning_rate_pct"] = (
        user_summary["flagged_tasks"] / user_summary["total_tasks"]
    ) * 100

    repeat_users = (
        user_summary[user_summary["total_tasks"] > 1]
        .sort_values(["flagged_tasks", "total_tasks"], ascending=False)
        .copy()
    )

    return user_summary, repeat_users


def identify_passthrough_cohort(df: pd.DataFrame) -> pd.DataFrame:
    """
    Isolate zero-review pass-through submissions:
    Tasks exhibiting extreme low TER + extreme CPS + exact unchanged Whisper text.
    """
    mask = (
        df["flag_extreme_low_ter"]
        & df["flag_extreme_cps"]
        & df["is_transcript_unchanged"]
    )
    return df[mask].copy()


def identify_block_candidates(
    df: pd.DataFrame,
    min_tasks: int = 5,
    blank_rate_threshold: float = 2.0,
    ter_below_1_rate_threshold: float = 30.0,
) -> pd.DataFrame:
    """
    Identify repeat transcribers qualifying for manual review under the proposed governance policy.

    Criteria:
    - Minimum task history: total_tasks >= min_tasks
    - Multiple concurrent warning signals (>= 2 signals):
        1. blank_rate > 2%
        2. extreme_ter_rate > 0%
        3. high_cps_rate > 0%
        4. ter_below_1_rate > 30%
    """
    # Calculate eligibility per task
    df_eval = df.copy()
    df_eval["blank_eligible"] = df_eval["duration_clean"].gt(1) & df_eval[
        "whisper_text"
    ].fillna("").ne("")
    df_eval["ter_eligible"] = df_eval["duration_clean"].gt(1) & df_eval["ter"].notna()
    df_eval["cps_eligible"] = (
        df_eval["duration_clean"].gt(5) & df_eval["user_task_cps"].notna()
    )

    users = (
        df_eval.groupby("user_id", dropna=False)
        .agg(
            total_tasks=("user_id", "size"),
            blank_tasks=("flag_blank_submission", "sum"),
            blank_eligible_tasks=("blank_eligible", "sum"),
            extreme_ter_tasks=("flag_extreme_low_ter", "sum"),
            ter_below_1_tasks=("flag_ter_below_1", "sum"),
            ter_eligible_tasks=("ter_eligible", "sum"),
            high_cps_tasks=("flag_extreme_cps", "sum"),
            cps_eligible_tasks=("cps_eligible", "sum"),
        )
        .reset_index()
    )

    def calc_rate(count, eligible):
        return np.where(eligible > 0, (count / np.maximum(eligible, 1)) * 100, 0.0)

    users["blank_rate"] = calc_rate(
        users["blank_tasks"], users["blank_eligible_tasks"]
    )
    users["extreme_ter_rate"] = calc_rate(
        users["extreme_ter_tasks"], users["ter_eligible_tasks"]
    )
    users["ter_below_1_rate"] = calc_rate(
        users["ter_below_1_tasks"], users["ter_eligible_tasks"]
    )
    users["high_cps_rate"] = calc_rate(
        users["high_cps_tasks"], users["cps_eligible_tasks"]
    )

    users["blank_signal"] = users["blank_rate"] > blank_rate_threshold
    users["extreme_ter_signal"] = users["extreme_ter_rate"] > 0
    users["high_cps_signal"] = users["high_cps_rate"] > 0
    users["ter_below_1_signal"] = (
        users["ter_below_1_rate"] > ter_below_1_rate_threshold
    )

    signal_cols = [
        "blank_signal",
        "extreme_ter_signal",
        "high_cps_signal",
        "ter_below_1_signal",
    ]
    users["warning_signal_count"] = users[signal_cols].sum(axis=1)

    users["block_candidate"] = (users["total_tasks"] >= min_tasks) & (
        users["warning_signal_count"] >= 2
    )

    users["candidate_reason"] = users.apply(
        lambda row: ", ".join(
            label
            for col, label in [
                ("blank_signal", "High blank rate"),
                ("extreme_ter_signal", "Extreme TER"),
                ("high_cps_signal", "High CPS"),
                ("ter_below_1_signal", "High TER<1 rate"),
            ]
            if row[col]
        )
        if row["block_candidate"]
        else "Does not meet policy threshold",
        axis=1,
    )

    return users.sort_values(
        ["block_candidate", "warning_signal_count", "total_tasks"],
        ascending=[False, False, False],
    )
