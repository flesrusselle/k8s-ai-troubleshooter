#!/usr/bin/env python3
"""Unified CLI for the k8s-ai-troubleshooter read-only workflows."""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

import collect  # noqa: E402
import session_log  # noqa: E402
from k8s_ai_core import investigate_bundle  # noqa: E402
from safety import SAFE_DIAGNOSTIC, SAFE_READ, classify  # noqa: E402

VERSION = "0.1.0-dev"
ALLOWED_AUTOMATIC_TIERS = {SAFE_READ, SAFE_DIAGNOSTIC}


def _add_collection_arguments(parser):
    parser.add_argument("--namespace", help="Namespace to investigate.")
    parser.add_argument("--all-namespaces", action="store_true",
                        help="Collect across every namespace.")
    parser.add_argument("--output", default="evidence-bundle",
                        help="Output directory (default: evidence-bundle).")
    parser.add_argument("--no-pods", action="store_true",
                        help="Skip per-pod describe and logs.")
    parser.add_argument("--no-optional", action="store_true",
                        help="Skip kubectl top and helm list.")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Per-command timeout in seconds (default: 60).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan and safety classifications without running it.")


def build_parser():
    parser = argparse.ArgumentParser(
        add_help=False,
        prog="k8s-ai",
        description="Read-only Kubernetes investigation and evidence tools.",
    )
    parser.add_argument("--help", action="help", help="Show this help message and exit.")
    parser.add_argument("--version", action="version", version=f"k8s-ai {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect", help="Collect a redacted, read-only evidence bundle.",
        add_help=False,
    )
    collect_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    _add_collection_arguments(collect_parser)

    safety_parser = subparsers.add_parser(
        "safety", help="Classify a command before considering execution.",
        add_help=False,
    )
    safety_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    safety_parser.add_argument("command_text", help="Command string to classify.")
    safety_parser.add_argument("--json", action="store_true",
                               help="Print the verdict as JSON.")

    sessions_parser = subparsers.add_parser(
        "sessions", help="Review recorded investigation and collection sessions.",
        add_help=False,
    )
    sessions_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    sessions_parser.add_argument("--tail", type=int, metavar="N",
                                 help="Print the last N entries.")
    sessions_parser.add_argument("--path", action="store_true",
                                 help="Print the resolved session log path.")
    sessions_parser.add_argument("--json", action="store_true",
                                 help="Print selected entries as JSON.")

    investigate_parser = subparsers.add_parser(
        "investigate", help="Analyze a previously collected evidence bundle.",
        add_help=False,
    )
    investigate_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    investigate_parser.add_argument("question", nargs="?", default="Investigate the evidence bundle",
                                    help="Question to answer.")
    investigate_parser.add_argument("--bundle", default="evidence-bundle",
                                    help="Evidence bundle directory (default: evidence-bundle).")
    investigate_parser.add_argument("--json", action="store_true",
                                    help="Print the structured report as JSON.")

    return parser


def _safety_payload(command):
    verdict = classify(command)
    return {
        "command": command,
        "safety": verdict.safety,
        "reason": verdict.reason,
        "automatic_execution_allowed": verdict.safety in ALLOWED_AUTOMATIC_TIERS,
    }


def _run_safety(args):
    payload = _safety_payload(args.command_text)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"Safety: {payload['safety']}")
        print(f"Automatic execution: {'yes' if payload['automatic_execution_allowed'] else 'no'}")
        print(f"Reason: {payload['reason']}")
    return 0


def _run_sessions(args):
    if args.path:
        print(session_log.log_path())
        return 0

    entries = session_log.read_entries()
    selected = entries[-args.tail:] if args.tail else entries
    if args.json:
        print(json.dumps(selected, sort_keys=True))
    elif args.tail:
        for entry in selected:
            print(json.dumps(entry, sort_keys=True))
    else:
        print(session_log.summarize(entries))
    return 0


def _run_collect(args):
    collect_args = []
    if args.namespace:
        collect_args += ["--namespace", args.namespace]
    if args.all_namespaces:
        collect_args.append("--all-namespaces")
    collect_args += ["--output", args.output, "--timeout", str(args.timeout)]
    if args.no_pods:
        collect_args.append("--no-pods")
    if args.no_optional:
        collect_args.append("--no-optional")
    if args.dry_run:
        collect_args.append("--dry-run")
    return collect.main(collect_args)


def _run_investigate(args):
    report = investigate_bundle(args.bundle, args.question)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0 if report.status != "UNAVAILABLE" else 2

    print(f"Status: {report.status}")
    print(f"Question: {report.question}")
    print(f"Bundle: {report.bundle}")
    if report.hypotheses:
        print("\nHypotheses:")
        for hypothesis in report.hypotheses:
            print(f"  - [{hypothesis.confidence}] {hypothesis.title}: {hypothesis.rationale}")
    if report.recommendations:
        print("\nRecommended next steps:")
        for recommendation in report.recommendations:
            print(f"  - {recommendation.action}")
    if report.unknowns:
        print("\nUnknowns:")
        for unknown in report.unknowns:
            print(f"  - {unknown}")
    return 0 if report.status != "UNAVAILABLE" else 2


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "collect":
        return _run_collect(args)
    if args.command == "safety":
        return _run_safety(args)
    if args.command == "sessions":
        return _run_sessions(args)
    if args.command == "investigate":
        return _run_investigate(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())