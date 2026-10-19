"""
Josh Talks AI — Question 2: Transcription Quality Analysis Pipeline.
Data-quality audit, suspicious-transcriber analysis, and governance framework.

This script executes the consolidated, reproducible analysis for:
- Part I: Task-level warning signs of poor-quality transcription
- Part II: Transcriber-level risk analysis, signal overlap, and governance audit
- Generates publication figures to reports/figures/
- Exports clean summary CSVs to outputs/

The original CSV remains strictly unchanged.
"""

from pathlib import Path
import pandas as pd

from src.audit import (
    preprocess_dataset,
    flag_task_warnings,
    compute_signal_overlap,
    aggregate_transcriber_risk,
    identify_passthrough_cohort,
    identify_block_candidates,
)
from src.visualization import generate_all_figures

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DATA_PATH = PROJECT_DIR / "data" / "raw" / "transcription_data.csv"
OUTPUT_DIR = PROJECT_DIR / "outputs"
REPORTS_DIR = PROJECT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"


def load_raw_data() -> pd.DataFrame:
    """Load the original CSV without modifying its contents."""
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at expected location: {RAW_DATA_PATH}\n"
            "Please refer to data/README.md for instructions on obtaining and placing the dataset."
        )

    df = pd.read_csv(RAW_DATA_PATH)
    print("Dataset loaded successfully.")
    print(f"Total Rows:    {df.shape[0]:,}")
    print(f"Total Columns: {df.shape[1]}")
    return df


def export_outputs(
    part1_summary: pd.DataFrame,
    overlap_matrix: pd.DataFrame,
    repeat_users: pd.DataFrame,
    block_candidates: pd.DataFrame,
    output_dir: Path,
):
    """Export summary metrics to outputs directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    part1_summary.to_csv(output_dir / "part1_warning_signals_summary.csv", index=False)
    overlap_matrix.to_csv(output_dir / "warning_signals_overlap_matrix.csv")
    repeat_users.to_csv(output_dir / "part2_repeat_users_audit.csv", index=False)
    block_candidates.to_csv(output_dir / "block_candidates.csv", index=False)
    print(f"Summary reports exported to: {output_dir}")


def main():
    print("=" * 70)
    print("JOSH TALKS AI — QUESTION 2 QUALITY AUDIT PIPELINE")
    print("=" * 70)

    # 1. Load data
    df_raw = load_raw_data()

    # 2. Preprocess & engineer features
    df = preprocess_dataset(df_raw)

    # 3. Part I Warning Flags
    df, thresh = flag_task_warnings(df)
    warning_cols = thresh["warning_cols"]

    print("\n--- PART I: WARNING SIGNALS ---")
    print(f"TER P1 Threshold:  {thresh['ter_p1']:.4f}")
    print(f"CPS P98 Threshold: {thresh['cps_p98']:.4f} chars/sec (duration > 5s)")

    counts = df[warning_cols].sum()
    pcts = (counts / len(df)) * 100

    part1_summary = pd.DataFrame({
        "signal_name": warning_cols,
        "flagged_tasks": counts.values,
        "percentage_of_all_tasks": pcts.round(2).values,
    })
    print(part1_summary.to_string(index=False))

    total_flagged = int(df["any_warning"].sum())
    total_pct = (total_flagged / len(df)) * 100
    print(f"\nUnique Flagged Tasks (Union): {total_flagged:,} ({total_pct:.2f}% of dataset)")

    # 4. Signal Overlap Matrix
    overlap_matrix = compute_signal_overlap(df, warning_cols)
    print("\n--- SIGNAL OVERLAP MATRIX ---")
    print(overlap_matrix)

    # 5. Part II User-Level Analysis
    user_summary, repeat_users = aggregate_transcriber_risk(df, warning_cols)
    total_users = len(user_summary)
    single_task_users = (user_summary["total_tasks"] == 1).sum()

    print("\n--- PART II: USER-LEVEL AUDIT ---")
    print(f"Total Unique Users:       {total_users:,}")
    print(f"Single-Task Users:        {single_task_users:,} ({(single_task_users / total_users) * 100:.2f}%)")
    print(f"Repeat Users (>1 task):   {len(repeat_users):,} ({(len(repeat_users) / total_users) * 100:.2f}%)")
    print(f"Total Tasks by Repeat:    {repeat_users['total_tasks'].sum():,}")

    print("\nTop Repeat Users Breakdown:")
    print(repeat_users.to_string(index=False))

    # 6. Zero-Review Pass-Through Analysis
    passthrough_df = identify_passthrough_cohort(df)
    print("\n--- ZERO-REVIEW PASS-THROUGH COHORT ---")
    print(f"Total Tasks (Extr. TER + High CPS + Unchanged Whisper): {len(passthrough_df)}")
    if len(passthrough_df) > 0:
        mean_time = passthrough_df["task_time_clean"].mean()
        is_edited_no = passthrough_df["is_edited"].eq("No").sum()
        print(f"Mean Task Time: {mean_time:.2f} seconds")
        print(f"Unedited Status ('No'): {is_edited_no} / {len(passthrough_df)} ({(is_edited_no / len(passthrough_df)) * 100:.1f}%)")

    # 7. Identify Governance Review Candidates
    block_candidates = identify_block_candidates(df)
    candidates_active = block_candidates[block_candidates["block_candidate"]].copy()
    print(f"\n--- GOVERNANCE REVIEW CANDIDATES (>= 5 tasks & >= 2 signals) ---")
    print(f"Candidates Flagged for Review: {len(candidates_active)}")
    if len(candidates_active) > 0:
        print(candidates_active[["user_id", "total_tasks", "blank_rate", "ter_below_1_rate", "candidate_reason"]].to_string(index=False))

    # 8. Export CSV artifacts
    export_outputs(part1_summary, overlap_matrix, repeat_users, candidates_active, OUTPUT_DIR)

    # 9. Generate Figures
    print("\n--- GENERATING REPORT FIGURES ---")
    generated_figures = generate_all_figures(df, thresh, overlap_matrix, repeat_users, FIGURES_DIR)
    for fig_p in generated_figures:
        print(f"Generated: {fig_p.name}")

    print("\nAudit pipeline completed successfully.")


if __name__ == "__main__":
    main()
