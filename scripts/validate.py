#!/usr/bin/env python3
"""
k8s-ai-troubleshooter Repository Structural & Schema Validation Script
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def validate_schemas():
    schemas_dir = REPO_ROOT / "schemas"
    required_schemas = ["runbook.schema.json", "decision-tree.schema.json", "command.schema.json"]
    for s in required_schemas:
        schema_path = schemas_dir / s
        if not schema_path.exists():
            raise FileNotFoundError(f"Missing schema: {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            json.load(f)
    print("✅ JSON Schemas are valid.")

def validate_runbooks():
    runbooks_dir = REPO_ROOT / "runbooks"
    required_sections = [
        "# ", "## Purpose", "## When to Use", "## Safety Level",
        "## Symptoms", "## Quick Diagnosis", "## Detailed Investigation",
        "## Decision Tree", "## Evidence to Collect", "## Root Cause Patterns",
        "## Confirmation", "## Remediation", "## Human Approval Required",
        "## Related Runbooks", "## Official Documentation"
    ]
    
    count = 0
    for file_path in runbooks_dir.rglob("*.md"):
        count += 1
        content = file_path.read_text(encoding="utf-8")
        for section in required_sections:
            if section not in content:
                raise ValueError(f"Runbook {file_path.name} missing required section: '{section}'")
    print(f"✅ All {count} Runbooks validated successfully.")

def validate_command_catalogs():
    commands_dir = REPO_ROOT / "commands"
    for cat in ["kubectl.yaml", "helm.yaml"]:
        cat_path = commands_dir / cat
        if not cat_path.exists():
            raise FileNotFoundError(f"Missing command catalog: {cat_path}")
    print("✅ Command Catalogs exist and are valid.")

LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")

def validate_links():
    """
    Resolve every local Markdown link relative to the file that contains it.

    Absolute file:// links are rejected outright: they encode one machine's
    directory layout, so they break for every other reader of the repository.
    """
    invalid_links = []
    checked = 0

    for file_path in sorted(REPO_ROOT.rglob("*.md")):
        if ".git" in file_path.parts:
            continue
        content = file_path.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            target = match.group(2).strip()
            if target.startswith(EXTERNAL_PREFIXES):
                continue

            rel = file_path.relative_to(REPO_ROOT)
            if target.startswith("file://"):
                invalid_links.append((rel, target, "absolute file:// link is not portable"))
                continue

            checked += 1
            resolved = (file_path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                invalid_links.append((rel, target, "target does not exist"))

    if invalid_links:
        print(f"❌ Found {len(invalid_links)} invalid local links:")
        for source, target, reason in invalid_links:
            print(f"  {source} -> {target} ({reason})")
        raise ValueError(f"{len(invalid_links)} invalid local links")

    print(f"✅ All {checked} internal file links validated.")

def main():
    print("🔍 Running k8s-ai-troubleshooter validation suite...")
    checks = [
        validate_schemas,
        validate_runbooks,
        validate_command_catalogs,
        validate_links,
    ]

    failures = []
    for check in checks:
        try:
            check()
        except Exception as exc:
            failures.append(f"{check.__name__}: {exc}")
            print(f"❌ {check.__name__} failed: {exc}")

    if failures:
        print(f"\n💥 {len(failures)} validation check(s) FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("🎉 All repository validations PASSED!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
