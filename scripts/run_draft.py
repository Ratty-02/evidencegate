"""Run the draft pipeline on one fixture dispute and print the report.

Usage (from the project root):
    python -m scripts.run_draft PP-R-0001
"""
import argparse

from app.ai.llm import GroqClient
from app.ai.pipeline import format_report, run_draft


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft and check a PayPal dispute response")
    parser.add_argument("dispute_id", help="e.g. PP-R-0001")
    args = parser.parse_args()
    report = run_draft(args.dispute_id, llm=GroqClient())
    print(format_report(report))


if __name__ == "__main__":
    main()
