#!/usr/bin/env python3
"""
k8s-ai-troubleshooter Local MCP Server Adapter

Provides Model Context Protocol tools for MCP-compatible AI clients to query
runbooks, decision trees, and command safety classifications.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from safety import classify, classify_command_safety  # noqa: E402

# `classify_command_safety` is re-exported so that callers which imported it
# from this module before the logic moved to scripts/safety.py keep working.
__all__ = ["load_runbooks_index", "query_command_safety", "classify_command_safety"]

def load_runbooks_index():
    runbooks_dir = REPO_ROOT / "runbooks"
    runbooks = []
    for file_path in runbooks_dir.rglob("*.md"):
        runbooks.append({
            "id": file_path.stem,
            "category": file_path.parent.name,
            "path": str(file_path.relative_to(REPO_ROOT))
        })
    return runbooks

def query_command_safety(command_str: str) -> dict:
    """
    Evaluate the safety classification of a kubectl or helm command.

    Classification logic lives in `scripts/safety.py`, which is the single
    implementation shared by this adapter and the test suite, and which is
    verified against `commands/*.yaml` in CI.
    """
    result = classify(command_str)
    return {
        "command": command_str,
        "safety": result.safety,
        "reason": result.reason,
        "automatic_execution_allowed": result.safety in ("SAFE_READ", "SAFE_DIAGNOSTIC"),
    }

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print(json.dumps({"status": "ok", "runbooks_count": len(load_runbooks_index())}))
        return

    if len(sys.argv) > 2 and sys.argv[1] == "--classify":
        print(json.dumps(query_command_safety(sys.argv[2]), indent=2))
        return

    print("k8s-ai-troubleshooter MCP server adapter running.")
    print(f"Loaded {len(load_runbooks_index())} runbooks from {REPO_ROOT}.")

if __name__ == "__main__":
    main()
