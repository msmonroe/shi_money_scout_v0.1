# Shi Money Scout

A small opportunity-finding agent designed to answer one question:

> "Which real opportunities are most likely to produce money soon, with the least painful acquisition effort?"

Shi Money Scout searches the web, extracts evidence, asks multiple local Ollama models for independent assessments, then applies a deterministic scoring layer. Models do **not** get to certify their own work.

Consensus is handled by a dedicated consensus agent that can enforce a reviewer quorum and apply disagreement penalties when models diverge too much.

## What it scores

Each opportunity is evaluated on:

- Existing buyer intent
- Revenue potential
- Fit with your skills
- Visible pain
- Urgency
- Decision-maker accessibility
- Time to first dollar
- Acquisition friction
- Competition
- Confidence the opportunity is real/current

The deterministic score is weighted. Model consensus is supplemental.

## Hard rejection rules

By default, Shi rejects or heavily penalizes opportunities that:

- have no identifiable buyer or employer
- have no evidence of an actual need
- appear stale or unverifiable
- require substantial unpaid speculative work
- depend primarily on high-volume cold calling
- have weak fit with configured skills
- are obviously low-value relative to effort

## Architecture

```text
Search
  ↓
Candidate URLs
  ↓
Page extraction
  ↓
Evidence record
  ↓
┌─────────────────────────────┐
│ Independent model reviewers │
│  Reviewer A / B / C         │
└─────────────┬───────────────┘
              ↓
       Consensus summary
              ↓
     Deterministic scorer
              ↓
       Ranked opportunities
```

## Quick start

Requires Python 3.10+ and Ollama running locally.

```bash
cd shi_money_scout
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python main.py
```

## Consensus Agent (multi-model)

Consensus settings live in `config.yaml` under `models.consensus`.

- `strategy`: `median` (default), `mean`, or `trimmed_mean`
- `min_reviewers`: minimum number of successful model reviews required
- `use_model_weights`: enable reviewer reliability weighting
- `model_weights`: per-model influence factors (example: stronger reviewer gets `1.3`, weaker gets `0.8`)
- `trim_ratio`: used by `trimmed_mean` to drop outlier extremes
- `disagreement_penalty.enabled`: whether disagreement should reduce final score
- `disagreement_penalty.stddev_threshold`: per-signal std-dev level considered high disagreement
- `disagreement_penalty.max_penalty_points`: cap on score reduction from disagreement
- `auto_calibration.*`: optional automatic model-weight tuning from historical run data

This creates a practical committee behavior:

- deterministic signals remain primary
- model consensus contributes secondary signal shaping
- reliability-weighted reviewers can influence consensus proportionally
- high model disagreement lowers confidence and reduces rank

### Auto-calibration

If `models.consensus.auto_calibration.enabled` is true, Shi will:

1. load prior opportunities from `history_file` (default: `output/opportunities.json`)
2. compute each model's historical average error against a target baseline (`deterministic_scores` by default)
3. convert lower error into higher weight, normalize around the median reviewer, clamp/smooth the result
4. optionally apply those weights at runtime (`apply_to_runtime: true`)
5. write diagnostics and suggested weights to `write_suggestions_file`

This gives you a lightweight feedback loop where better historical agreement gradually increases reviewer influence.

By default the search layer uses `ddgs` for web discovery and does not require a paid API key.

## Output

Results are written to:

- `output/opportunities.json`
- `output/report.md`

Live run status is also written to:

- `output/status.json`

To watch progress and ETA in real-time:

```bash
./watch_status.sh
```

Optional arguments:

```bash
./watch_status.sh output/status.json 1
```

That is: `status-file-path` then refresh interval in seconds.

## Important

This is a lead-ranking/research tool, not a financial adviser. It does not spend money, contact prospects, submit applications, or enter contracts. Those actions should stay human-approved.
