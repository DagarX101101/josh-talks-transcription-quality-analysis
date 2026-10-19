"""
Josh Talks Transcription Quality Analysis Package.
"""

from src.metrics import (
    calculate_ter,
    clean_text_series,
    count_non_space_characters,
    calculate_cps,
    derive_empirical_thresholds,
)
from src.audit import (
    preprocess_dataset,
    flag_task_warnings,
    compute_signal_overlap,
    aggregate_transcriber_risk,
    identify_passthrough_cohort,
    identify_block_candidates,
)
from src.visualization import generate_all_figures

__all__ = [
    "calculate_ter",
    "clean_text_series",
    "count_non_space_characters",
    "calculate_cps",
    "derive_empirical_thresholds",
    "preprocess_dataset",
    "flag_task_warnings",
    "compute_signal_overlap",
    "aggregate_transcriber_risk",
    "identify_passthrough_cohort",
    "identify_block_candidates",
    "generate_all_figures",
]
