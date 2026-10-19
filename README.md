# Josh Talks Transcription Quality Analysis & Monitoring Framework

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-11%20passed-brightgreen.svg)](tests/)
[![Code Style](https://img.shields.io/badge/code%20style-pep8-orange.svg)](src/)

An empirical data audit, behavioral heuristic modeling, and automated quality governance pipeline for crowdsourced audio transcription platforms.

---

## 📌 Project Overview & Purpose

In crowdsourced speech transcription workflows, contributors review pre-populated Automatic Speech Recognition (ASR) baselines (e.g., OpenAI Whisper) and correct transcription errors against audio recordings. Because contributors are compensated based on task completion, platforms often face operational challenges including:
- **Zero-review pass-through:** Submitting pre-populated ASR text without listening or editing.
- **Premature blank submissions:** Marking audio clips as `[blank]` to rapidly collect rewards despite clear speech content.
- **Rushed reviews:** Submitting transcripts faster than physical playback duration allows.

This project delivers an end-to-end, reproducible framework to detect task-level submission anomalies, evaluate repeat-contributor risk profiles, and establish a balanced human-in-the-loop review workflow.

---

## 📊 Dataset Overview (Verified Statistics)

The analysis was performed on the official internal evaluation dataset containing **51,783** task submissions across **48,875** unique contributor accounts:

| Parameter | Verified Statistic | Interpretation |
|:---|:---:|:---|
| **Total Task Submissions** | **51,783** | Complete production evaluation export |
| **Unique Contributor IDs** | **48,875** | Large, distributed user base |
| **Single-Task Contributors** | **48,865 (99.98%)** | Severe account churn / fragmentation |
| **Repeat Contributors ($N > 1$)** | **10 (0.02%)** | 10 contributors completed 2,918 tasks |
| **Tasks Flagged by Any Signal** | **6,832 (13.19%)** | Union of all 4 warning signals |
| **Clean Baseline Submissions** | **44,951 (86.81%)** | Submissions exhibiting zero warning signals |

> **Data Privacy Note:** In accordance with confidentiality and data protection standards, the raw audio dataset (`transcription_data.csv`) is preserved locally and excluded from Git tracking via `.gitignore`. See [`data/README.md`](data/README.md) for instructions on placing the dataset.

---

## 🔍 Key Warning Signals & Empirical Thresholds

Four orthogonal warning indicators were derived from the empirical distributions of task timing, audio duration, and character throughput:

```text
                               TASK-LEVEL WARNING SIGNALS
 ─────────────────────────────────────────────────────────────────────────────────────────
  Signal Name              Empirical Rule / Filter                Count    Share of Dataset
 ─────────────────────────────────────────────────────────────────────────────────────────
  flag_ter_below_1         TER < 1.0 (Task Time < Audio Duration) 5,939        11.47%
  flag_blank_submission    Empty / [blank] with Whisper present    1,019         1.97%
  flag_extreme_low_ter     TER < 0.1788 (Bottom 1st Percentile)      517         1.00%
  flag_extreme_cps         CPS > 59.86 chars/sec (Top 2nd Pctile)    457         0.88%
 ─────────────────────────────────────────────────────────────────────────────────────────
  Union of Any Warning     At least 1 warning signal triggered    6,832        13.19%
```

![Warning Signals Distribution](reports/figures/warning_signals_distribution.png)

### Metric Definitions:
1. **Task-to-Audio Time Ratio (TER):**
   $$\text{TER} = \frac{\text{time\_taken\_by\_user}}{\text{duration}}$$
   - $\text{TER} < 1.0$: Transcriber spent less time than the real-time audio playback length.
   - $\text{TER} < 0.1788$: Bottom 1st percentile of valid tasks (audio duration $> 1.0$s).
2. **Character Throughput Speed (CPS):**
   $$\text{CPS} = \frac{\text{non\_space\_characters}}{\text{time\_taken\_by\_user}}$$
   - $\text{CPS} > 59.8576$: Top 2nd percentile of character production rate for clips $> 5.0$s (equivalent to $\sim 700$ words per minute, far exceeding normal human typing capacity of 40–80 WPM).
3. **Blank / Incomplete Submissions:**
   - User submitted `""` or literal `[blank]` while Whisper transcribed non-empty text on audio clips $> 1.0$s.

---

## 🔬 Key Empirical Findings

### 1. The Zero-Review Pass-Through Cohort
- Cross-tabulation of signals identified **346 tasks** that simultaneously trigger `flag_extreme_low_ter` and `flag_extreme_cps` with exact text matching `user_text == whisper_text`.
- **100% of these tasks** have recorded platform edit status `"No"`.
- The average elapsed task time was **1.81 seconds**, confirming zero-review click-through behavior.
- *All 346 instances originated from single-task accounts.*

### 2. Longitudinal Skew & Repeat Contributor Audit
- 10 repeat transcribers completed between 86 and 609 tasks each (totaling 2,918 tasks).
- All 10 repeat users had overall warning rates between **24.8% and 33.9%**.
- However, their flags were almost exclusively driven by moderate rushing ($TER < 1.0$). **None** of the repeat users exhibited extreme burst anomalies ($CPS > 59.86$).

![Repeat Transcribers Risk Profile](reports/figures/repeat_transcribers_risk_profile.png)

---

## 🛡️ Proposed Governance & Review Policy

> **Important:** Warning signals are probabilistic triage filters, not conclusive evidence of misconduct. A low TER may occasionally occur when an experienced contributor reviews a crystal-clear audio snippet at $1.5\times$ speed.

As detailed in [`docs/enforcement-rules.md`](docs/enforcement-rules.md), we propose a multi-tiered review protocol:

1. **Audit Candidacy Criteria:** An account is prioritized for audit if it has completed $\ge 5$ tasks and triggers at least **two** of the following:
   - Blank submission rate $> 2.0\%$
   - Extreme low TER rate $> 0.0\%$
   - Extreme CPS rate $> 0.0\%$
   - Rushing rate ($TER < 1.0$) $> 30.0\%$
2. **Current Audit Candidates:** Exactly **3 transcribers** meet these criteria in the dataset (User IDs `580062`, `632098`, and `326611`), driven by elevated blank submission rates combined with high $TER < 1.0$ rates.
3. **Mandatory Human Verification:** Before any punitive action, an auditor must manually listen to a 10-task sample and compute ground-truth Character Error Rate (CER).
4. **Graduated Remediation:**
   - *First Infraction:* Educational feedback notice.
   - *Persistent Issues:* Task requeueing and batch-size throttling.
   - *Confirmed System Exploitation:* Account offboarding with a 14-day appeals window.

---

## 📁 Repository Structure

```text
josh-talks-transcription-quality-analysis/
├── README.md                      # Primary project documentation
├── requirements.txt               # Pinned third-party dependencies
├── .gitignore                     # Data privacy, virtualenv & cache exclusions
├── LICENSE                        # MIT Open Source License
├── analysis.py                    # Root execution pipeline script
├── data/
│   ├── README.md                  # Dataset placement guide & privacy notes
│   └── raw/
│       └── .gitkeep               # Directory placeholder (raw CSV ignored)
├── src/
│   ├── __init__.py                # Package exports
│   ├── metrics.py                 # Core math, TER, CPS & quantile thresholding
│   ├── audit.py                   # Warning flags, signal overlap & risk grouping
│   └── visualization.py          # Publication-grade chart generation
├── reports/
│   ├── README.md                  # Detailed analytical report
│   └── figures/                   # High-resolution generated charts
│       ├── warning_signals_distribution.png
│       ├── ter_distribution.png
│       ├── cps_throughput_distribution.png
│       ├── signals_overlap_heatmap.png
│       └── repeat_transcribers_risk_profile.png
├── outputs/                       # Verified analytical summary CSVs
│   ├── part1_warning_signals_summary.csv
│   ├── warning_signals_overlap_matrix.csv
│   ├── part2_repeat_users_audit.csv
│   └── block_candidates.csv
├── notebooks/
│   └── 01_data_quality_and_cleaning.ipynb # Interactive EDA & audit notebook
├── docs/
│   └── enforcement-rules.md       # Comprehensive policy & governance framework
└── tests/
    ├── __init__.py                # Test package init
    ├── test_metrics.py            # Unit tests for core math & edge cases
    └── test_audit.py              # Unit tests for audit flags & aggregation
```

---

## 🚀 Setup & Execution Guide

### 1. Environment Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/DagarX101101/josh-talks-transcription-quality-analysis.git
cd josh-talks-transcription-quality-analysis

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 2. Dataset Placement

Ensure `transcription_data.csv` is placed in `data/raw/`:
```text
data/raw/transcription_data.csv
```
*(Refer to [`data/README.md`](data/README.md) for details)*

### 3. Run the Quality Audit Pipeline

Execute the end-to-end analysis script:

```bash
python analysis.py
```

This will:
1. Load and clean the raw 51,783 task records.
2. Calculate empirical thresholds ($TER_{p1} = 0.1788$, $CPS_{p98} = 59.8576$).
3. Apply task-level warning flags and generate the co-occurrence matrix.
4. Profile repeat transcribers and identify review candidates.
5. Export verified CSV summaries to `outputs/`.
6. Generate 5 publication-quality figures into `reports/figures/`.

### 4. Run Unit Tests

Execute the automated test suite:

```bash
# Using standard Python unittest
python -m unittest discover tests

# Or using pytest (if installed)
pytest tests/ -v
```

---

## ⚠️ Limitations & Future Improvements

1. **Lack of Consensus Ground Truth:** The dataset contains user transcripts and Whisper baselines, but no verified gold-standard human consensus transcripts. As a result, Character Error Rate (CER) and Word Error Rate (WER) cannot be computed directly without manual listening.
2. **Single-Task Contributor Domination:** 99.98% of transcribers submitted only one task, limiting longitudinal modeling. Onboarding gamification and progressive task unlocks could improve user retention.
3. **Voice Activity Detection (VAD):** Incorporating acoustic VAD models (such as Silero VAD) would automatically identify silent or noisy audio segments, eliminating false-positive blank submission flags on genuine silence.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
