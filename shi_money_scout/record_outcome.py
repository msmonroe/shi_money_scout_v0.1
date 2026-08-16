from argparse import ArgumentParser
from pathlib import Path

from shi.outcomes import STAGE_SCORES, record_outcome


ROOT = Path(__file__).resolve().parent
OUTCOMES = ROOT / "output" / "outcomes.json"


def main():
    parser = ArgumentParser(description="Record a real-world outcome for a Money Scout opportunity.")
    parser.add_argument("url", help="Opportunity URL")
    parser.add_argument("stage", choices=sorted(STAGE_SCORES), help="Funnel stage reached")
    parser.add_argument("--amount", type=float, default=None, help="Revenue/offer amount when useful")
    parser.add_argument("--notes", default="", help="Optional short note")
    args = parser.parse_args()

    row = record_outcome(OUTCOMES, args.url, args.stage, args.amount, args.notes)
    print(f"Recorded {row['stage']} for {row['opportunity_id']}")
    if row.get("amount") is not None:
        print(f"Amount: {row['amount']}")
    print(f"Outcomes file: {OUTCOMES}")


if __name__ == "__main__":
    main()
