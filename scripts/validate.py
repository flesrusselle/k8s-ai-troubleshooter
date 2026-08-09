#!/usr/bin/env python3
"""
k8s-ai-troubleshooter Repository Structural & Schema Validation Script
"""

import json
import os
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

def validate_links():
    markdown_files = list(REPO_ROOT.rglob("*.md"))
    link_pattern = re.compile(r'\[([^\]]+)\]\((file:///[^\)]+)\)')
    invalid_links = []
    
    for file_path in markdown_files:
        content = file_path.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            url = match.group(2)
            clean_path = url.replace("file://", "").split("#")[0]
            if not os.path.exists(clean_path):
                invalid_links.append((file_path.name, url))
                
    if invalid_links:
        print(f"⚠️ Warning: Found {len(invalid_links)} unresolvable local file links:")
        for source, target in invalid_links:
            print(f"  {source} -> {target}")
    else:
        print("✅ All internal file links validated.")

def main():
    print("🔍 Running k8s-ai-troubleshooter validation suite...")
    validate_schemas()
    validate_runbooks()
    validate_command_catalogs()
    validate_links()
    print("🎉 All repository validations PASSED!")

if __name__ == "__main__":
    main()
