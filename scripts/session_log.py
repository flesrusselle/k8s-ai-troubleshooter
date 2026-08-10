#!/usr/bin/env python3
"""
Session/audit log for k8s-ai-troubleshooter.

Every other tool here answers "what should happen right now." Nothing answers
"what happened last time" — the same OOMKilled pod recurring three times this
quarter is invisible, and there is no way to check whether a "High confidence"
diagnosis was actually right. This module is the minimum viable fix: append one
JSON object per diagnosis or collection run to a local, git-ignored JSONL file,
and give it a `--summary` view.

This is deliberately not a database, a metrics pipeline, or a dashboard. It is
the smallest thing that makes "did we see this before?" answerable, and the
foundation a future confidence-calibration check — comparing declared
confidence against actual outcome — would build on.

Log location resolution:

1. $K8S_AI_TROUBLESHOOTER_SESSION_LOG, for a shared or team-wide location;
2. ./.k8s-ai-troubleshooter/sessions.jsonl, relative to the current working
   directory, created on first write.

Two sources write to it today:

- `scripts/collect.py`, one entry per evidence-collection run — what was
  scoped, how many unhealthy pods were found, whether anything was redacted;
- `integrations/mcp/server.py`'s `log_diagnosis` tool, one entry per
  conclusion an assistant reaches — signal, routed runbook, confidence, root
  cause. This is the richer of the two, since only the assistant knows the
  confidence and the cause; the collector only knows what it gathered.
"""

import argparse
import collections
import datetime
import json
import os
import sys
import uuid
from pathlib import Path

DEFAULT_LOG_PATH = Path(".k8s-ai-troubleshooter") / "sessions.jsonl"


def log_path():
    override = os.environ.get("K8S_AI_TROUBLESHOOTER_SESSION_LOG")
    return Path(override) if override else DEFAULT_LOG_PATH


def record(source, **fields):
    """
    Append one entry to the session log and return it.

    `source` identifies what created the entry ("collect", "mcp", "manual").
    Fields left as None are omitted from the entry rather than written as
    null, so the log stays easy to grep and callers like `summarize` don't
    have to special-case None everywhere.
    """
    entry = {
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source,
    }
    entry.update({k: v for k, v in fields.items() if v is not None})

    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_entries(path=None):
    """
    Return every entry in the log, oldest first.

    A corrupted line — a truncated write from a crash, a concurrent-write
    interleave — is skipped rather than aborting the read; one bad line must
    not hide every entry around it.
    """
    path = path or log_path()
    if not path.exists():
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def summarize(entries):
    """Human-readable counts by runbook, confidence, and source."""
    if not entries:
        return "No sessions recorded yet."

    by_runbook = collections.Counter(e.get("runbook", "(unrouted)") for e in entries)
    by_confidence = collections.Counter(e.get("confidence", "(not stated)") for e in entries)
    by_source = collections.Counter(e.get("source", "(unknown)") for e in entries)

    lines = [f"{len(entries)} session(s) recorded.", "", "By runbook:"]
    for runbook, count in by_runbook.most_common(15):
        lines.append(f"  {count:4}  {runbook}")

    lines += ["", "By confidence:"]
    for confidence, count in by_confidence.most_common():
        lines.append(f"  {count:4}  {confidence}")

    lines += ["", "By source:"]
    for source, count in by_source.most_common():
        lines.append(f"  {count:4}  {source}")

    recurring = sorted(
        runbook for runbook, count in by_runbook.items()
        if count >= 3 and runbook != "(unrouted)"
    )
    if recurring:
        lines += ["", "Recurring (3+ times) — worth investigating the pattern, not just the instance:"]
        lines += [f"  - {runbook}" for runbook in recurring]

    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Review the k8s-ai-troubleshooter session log.",
    )
    parser.add_argument("--summary", action="store_true",
                        help="Print counts by runbook, confidence, and source (default).")
    parser.add_argument("--tail", type=int, metavar="N",
                        help="Print the last N entries as JSON, one per line.")
    parser.add_argument("--path", action="store_true",
                        help="Print the resolved log path and exit.")
    args = parser.parse_args(argv)

    if args.path:
        print(log_path())
        return 0

    entries = read_entries()

    if args.tail:
        for entry in entries[-args.tail:]:
            print(json.dumps(entry, sort_keys=True))
        return 0

    print(summarize(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
