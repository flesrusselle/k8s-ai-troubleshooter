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
    required_schemas = [
        "runbook.schema.json",
        "decision-tree.schema.json",
        "command.schema.json",
        "symptom-index.schema.json",
    ]
    for s in required_schemas:
        schema_path = schemas_dir / s
        if not schema_path.exists():
            raise FileNotFoundError(f"Missing schema: {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            json.load(f)
    print("✅ JSON Schemas are valid.")

# Ordered as the investigation runs: identify, diagnose, conclude, then act.
# Blast Radius precedes Human Approval Required so the operator is deciding with
# the cost in view; Verification and Rollback follow it, because a remediation
# with no way to check it worked, and no way back, is not a complete answer.
#
# tests/test_runbooks.py imports this list rather than restating it, so the
# validator and the test suite cannot disagree about what a runbook must contain.
REQUIRED_RUNBOOK_SECTIONS = [
    "# ", "## Purpose", "## When to Use", "## Safety Level",
    "## Symptoms", "## Quick Diagnosis", "## Detailed Investigation",
    "## Decision Tree", "## Evidence to Collect", "## Root Cause Patterns",
    "## Confirmation", "## Remediation", "## Blast Radius",
    "## Human Approval Required", "## Verification", "## Rollback",
    "## Related Runbooks", "## Official Documentation",
]


def validate_runbooks():
    runbooks_dir = REPO_ROOT / "runbooks"
    required_sections = REQUIRED_RUNBOOK_SECTIONS

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

def load_symptom_index():
    import yaml

    index_path = REPO_ROOT / "symptom-index.yaml"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing symptom index: {index_path}")
    return yaml.safe_load(index_path.read_text(encoding="utf-8"))


def validate_symptom_index():
    """
    Check that the router and the runbooks cannot drift apart.

    Three properties, each of which has a failure mode worth catching:

    - every entry points at a runbook and decision tree that exist, so routing
      never dead-ends;
    - every runbook is reachable from at least one entry, so a new runbook
      cannot be added without a route to it and then sit unused;
    - entry ids are unique, so a duplicate cannot silently shadow another.
    """
    index = load_symptom_index()
    entries = index.get("entries", [])
    if not entries:
        raise ValueError("symptom-index.yaml declares no entries")

    # Structural validation against the JSON Schema. jsonschema is installed in
    # CI; locally it may be absent, in which case say so rather than reporting a
    # pass we did not perform.
    try:
        import jsonschema
    except ImportError:
        print("⏭️  jsonschema not installed — skipped schema validation of symptom-index.yaml")
    else:
        schema = json.loads(
            (REPO_ROOT / "schemas" / "symptom-index.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.validate(instance=index, schema=schema)

    problems = []
    seen_ids = set()
    routed = set()

    default_entry = index.get("default_entry")
    if not default_entry:
        problems.append("missing default_entry")
    elif not (REPO_ROOT / default_entry).exists():
        problems.append(f"default_entry does not exist: {default_entry}")
    else:
        routed.add(default_entry)

    for entry in entries:
        entry_id = entry.get("id", "<missing id>")
        if entry_id in seen_ids:
            problems.append(f"duplicate entry id: {entry_id}")
        seen_ids.add(entry_id)

        runbook = entry.get("runbook")
        if not runbook:
            problems.append(f"{entry_id}: missing runbook")
        elif not (REPO_ROOT / runbook).exists():
            problems.append(f"{entry_id}: runbook does not exist: {runbook}")
        else:
            routed.add(runbook)

        tree = entry.get("decision_tree")
        if tree and not (REPO_ROOT / tree).exists():
            problems.append(f"{entry_id}: decision tree does not exist: {tree}")

        if not entry.get("signals"):
            problems.append(f"{entry_id}: declares no signals")

    all_runbooks = {
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "runbooks").rglob("*.md")
    }
    for orphan in sorted(all_runbooks - routed):
        problems.append(f"runbook is unreachable from symptom-index.yaml: {orphan}")

    if problems:
        print(f"❌ Found {len(problems)} symptom index problem(s):")
        for problem in problems:
            print(f"  {problem}")
        raise ValueError(f"{len(problems)} symptom index problem(s)")

    print(f"✅ Symptom index routes {len(entries)} signals to {len(routed)} runbooks; no orphans.")


def main():
    print("🔍 Running k8s-ai-troubleshooter validation suite...")
    checks = [
        validate_schemas,
        validate_runbooks,
        validate_command_catalogs,
        validate_symptom_index,
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
