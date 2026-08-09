#!/usr/bin/env python3
"""
k8s-ai-troubleshooter Local MCP Server Adapter

Provides Model Context Protocol tools for MCP-compatible AI clients to query
runbooks, decision trees, and command safety classifications.
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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

def classify_command_safety(command_str: str) -> str:
    """
    Evaluates safety classification of a given command string.
    """
    cmd = command_str.strip().lower()
    destructive_keywords = ["delete namespace", "delete pvc", "delete pod --force", "uninstall"]
    approval_keywords = ["rollout restart", "scale", "patch", "apply", "replace", "edit", "upgrade", "rollback", "delete"]
    
    for kw in destructive_keywords:
        if kw in cmd:
            return "DESTRUCTIVE"
            
    for kw in approval_keywords:
        if kw in cmd:
            return "HUMAN_APPROVAL_REQUIRED"
            
    if cmd.startswith("kubectl get") or cmd.startswith("kubectl describe") or cmd.startswith("kubectl logs") or cmd.startswith("helm status") or cmd.startswith("helm list"):
        return "SAFE_READ"
        
    if cmd.startswith("kubectl top") or cmd.startswith("kubectl explain"):
        return "SAFE_DIAGNOSTIC"
        
    return "HUMAN_APPROVAL_REQUIRED"

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print(json.dumps({"status": "ok", "runbooks_count": len(load_runbooks_index())}))
        return

    print("k8s-ai-troubleshooter MCP server adapter running.")
    print(f"Loaded {len(load_runbooks_index())} runbooks from {REPO_ROOT}.")

if __name__ == "__main__":
    main()
