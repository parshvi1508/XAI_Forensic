"""
CLI entry point for lime-audit.

Usage:
    lime-audit run --model distilbert/distilbert-base-uncased-finetuned-sst-2-english
    lime-audit run --model <name> --test-set my_inputs.json --output results/
    lime-audit report --output results/
    lime-audit charts --output results/
"""

import argparse
import sys

from lime_audit import __version__


DEFAULT_MODEL = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"


def cmd_run(args):
    from lime_audit.runner import run_audit
    output_dir = run_audit(
        model_name=args.model,
        test_set_path=args.test_set if args.test_set else None,
        output_dir=args.output if args.output else None,
    )
    if not args.skip_report:
        from lime_audit.analyse import analyse
        analyse(output_dir, args.model)
    if not args.skip_charts:
        from lime_audit.charts import generate_charts
        generate_charts(output_dir)


def cmd_report(args):
    from lime_audit.analyse import analyse
    analyse(args.output, args.model)


def cmd_charts(args):
    from lime_audit.charts import generate_charts
    generate_charts(args.output)


def main():
    parser = argparse.ArgumentParser(
        prog="lime-audit",
        description="Audit LIME explanations for stability and faithfulness",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full LIME audit")
    run_parser.add_argument("--model", default=DEFAULT_MODEL, help="HuggingFace model name (default: distilbert-sst2)")
    run_parser.add_argument("--test-set", default=None, help="Path to test set JSON (default: bundled 30 inputs)")
    run_parser.add_argument("--output", default=None, help="Output directory (default: ./lime_audit_results)")
    run_parser.add_argument("--skip-report", action="store_true", help="Skip analysis report after run")
    run_parser.add_argument("--skip-charts", action="store_true", help="Skip chart generation after run")
    run_parser.set_defaults(func=cmd_run)

    report_parser = subparsers.add_parser("report", help="Generate analysis report from existing results")
    report_parser.add_argument("--output", default="lime_audit_results", help="Results directory")
    report_parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name (for tokenizer mismatch)")
    report_parser.set_defaults(func=cmd_report)

    charts_parser = subparsers.add_parser("charts", help="Generate charts from existing results")
    charts_parser.add_argument("--output", default="lime_audit_results", help="Results directory")
    charts_parser.set_defaults(func=cmd_charts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
