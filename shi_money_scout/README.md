# Shi Money Scout

A small opportunity-finding agent designed to answer one question:

> "Which real opportunities are most likely to produce money soon, with the least painful acquisition effort?"

Shi Money Scout searches the web, extracts evidence, asks multiple local Ollama models for independent assessments, then applies a deterministic scoring layer. Models do **not** get to certify their own work.

The current design has three important safeguards:

1. deterministic page evidence remains the primary scoring signal
2. model reviewers must provide verbatim evidence quotes that are checked against fetched page text
3. real-world outcomes can be recorded so future calibration can move toward actual response/interview/revenue data instead of self-referential model scores

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
Deterministic evidence record
  ↓
┌─────────────────────────────┐
│ Independent model reviewers │
│  Reviewer A / B / C         │
└─────────────┬───────────────┘
              ↓
      Quote verification
              ↓
       Consensus summary
              ↓
     Deterministic scorer
              ↓
       Ranked opportunities
              ↓
       Real-world outcome
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

Run the built-in tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Evidence verification

The reviewer schema now requires evidence like:

```json
{
  "claim": "The role is a 12 month contract",
  "quote": "12 month contract"
}
```

`quote` must occur in the fetched page text. Shi verifies the quote deterministically and removes unverified evidence before consensus. A configurable evidence-quality penalty lowers the final score when reviewers repeatedly provide unsupported evidence.

This is intentionally designed to catch the dangerous failure mode where an LLM invents a convincing fact, citation, salary, deadline, or requirement.

## Consensus Agent (multi-model)

Consensus settings live in `config.yaml` under `models.consensus`.

- `strategy`: `median` (default), `mean`, or `trimmed_mean`
- `min_reviewers`: minimum number of successful model reviews required
- `use_model_weights`: enable reviewer reliability weighting
- `model_weights`: per-model influence factors
- `trim_ratio`: used by `trimmed_mean` to drop outlier extremes
- `disagreement_penalty.*`: reduces score when reviewers disagree heavily
- `evidence_penalty.*`: reduces score when reviewer quotes cannot be verified
- `auto_calibration.*`: optional automatic model-weight tuning from historical run data

Deterministic signals remain primary. Model consensus shapes the result but does not control it.

### Auto-calibration

The existing auto-calibration system can compare reviewers with a historical baseline and adjust reviewer weights. Its default target is still `deterministic_scores`.

Treat that target as provisional. The stronger long-term direction is calibration against **real outcomes**, not against Shi's own heuristics.

## Real-world outcome tracking

Every opportunity now gets a stable `opportunity_id`, and Shi reads optional history from:

```text
output/outcomes.json
```

Record what actually happened with:

```bash
python record_outcome.py "https://example.com/opportunity" pursued
python record_outcome.py "https://example.com/opportunity" response
python record_outcome.py "https://example.com/opportunity" interview
python record_outcome.py "https://example.com/opportunity" proposal
python record_outcome.py "https://example.com/opportunity" offer --amount 120000
python record_outcome.py "https://example.com/opportunity" paid --amount 5000 --notes "first invoice paid"
```

Supported stages are:

- surfaced
- pursued
- response
- interview
- proposal
- offer
- paid
- rejected
- ignored

The point is to build the dataset needed for a future ranking model that can answer a much more useful question:

> "Which characteristics actually led to responses, interviews, offers, and money?"

## Output

Results are written to:

- `output/opportunities.json`
- `output/report.md`
- `output/status.json`
- `output/outcomes.json` when outcome tracking is used

To watch progress and ETA in real-time:

```bash
./watch_status.sh
```

Optional arguments:

```bash
./watch_status.sh output/status.json 1
```

## Important

This is a lead-ranking/research tool, not a financial adviser. It does not spend money, contact prospects, submit applications, or enter contracts. Those actions stay human-approved.
