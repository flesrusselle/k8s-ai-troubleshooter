#!/usr/bin/env python3
"""
PR Release Preview Generator for k8s-ai-troubleshooter

Generates structured Release Preview markdown based on Git diff.
Formated using Asia/Manila (PHT) timestamps.
"""

import datetime
import os
import subprocess
import sys
from pathlib import Path

# Try timezone import or fallback
try:
    import zoneinfo
    PHT_TZ = zoneinfo.ZoneInfo("Asia/Manila")
except Exception:
    # Standard UTC+8 offset fallback for Asia/Manila
    PHT_TZ = datetime.timezone(datetime.timedelta(hours=8))

def format_pht_timestamp(dt: datetime.datetime) -> str:
    """
    Format timestamp as e.g. 'August 9, 2026 — 9:52 PM PHT'
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(PHT_TZ)
    else:
        dt = dt.astimezone(PHT_TZ)
        
    date_str = dt.strftime("%B %d, %Y")
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    return f"{date_str} — {time_str} PHT"

def get_git_diff_summary():
    added, modified, deleted = [], [], []
    try:
        res = subprocess.run(["git", "status", "--porcelain", "-uall"], capture_output=True, text=True, check=True)
        lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
        
        for line in lines:
            status = line[:2]
            filepath = line[3:].strip()
            if "?" in status or "A" in status:
                added.append(filepath)
            elif "M" in status:
                modified.append(filepath)
            elif "D" in status:
                deleted.append(filepath)
    except Exception:
        pass

    if not added and not modified:
        repo_root = Path(__file__).resolve().parent.parent
        for folder in ["runbooks", "decision-trees", "commands", "integrations"]:
            dir_path = repo_root / folder
            if dir_path.exists():
                for p in dir_path.rglob("*"):
                    if p.is_file():
                        added.append(str(p.relative_to(repo_root)))
                        
    return added, modified, deleted

def generate_release_preview(created_at: datetime.datetime = None):
    now = datetime.datetime.now(PHT_TZ)
    if created_at is None:
        created_at = now
        
    added, modified, deleted = get_git_diff_summary()
    
    runbooks_added = [f for f in added if f.startswith("runbooks/")]
    trees_added = [f for f in added if f.startswith("decision-trees/")]
    commands_added = [f for f in added if f.startswith("commands/")]
    integrations_added = [f for f in added if f.startswith("integrations/")]
    
    preview_md = f"""# 🚀 Release Preview

## Summary
Initial release of `k8s-ai-troubleshooter` — an open-source, model-agnostic, deterministic Kubernetes troubleshooting engine and diagnostic runbook system.

## Added
- **Runbooks**: {len(runbooks_added)} diagnostic runbooks added covering Pods, Networking, Storage, Nodes, Deployments, and Helm.
- **Decision Trees**: {len(trees_added)} machine-readable YAML decision trees.
- **Command Catalogs**: Classified `kubectl.yaml` and `helm.yaml` command catalogs.
- **AI Integrations**: Antigravity (`SKILL.md`), Claude Code (`CLAUDE.md`), Cursor (`.cursorrules`), ChatGPT, Copilot, Generic AI Prompt, and MCP Server adapter.

## Runbooks
{chr(10).join(f"- `{f}`" for f in runbooks_added) if runbooks_added else "- Core diagnostic runbooks set established."}

## Decision Trees
{chr(10).join(f"- `{f}`" for f in trees_added) if trees_added else "- Declarative pod, networking, storage, node, and helm trees."}

## Commands
- Classified safety levels: `SAFE_READ`, `SAFE_DIAGNOSTIC`, `HUMAN_APPROVAL_REQUIRED`, `DESTRUCTIVE`.

## AI Integrations
- Native Antigravity Skill, Claude Code instructions, Cursor rules, ChatGPT/Copilot instructions, MCP server adapter.

## Helm
- Helm release ownership tracing and values investigation guidelines added.

## Security
- **Strict Read-Only Default**: Zero automated state mutation allowed.
- **Human Approval**: State-changing commands explicitly require human operator consent.

## Testing
- JSON Schema validation
- Runbook section completeness check
- Python offline test suite (`pytest` / `unittest`)
- Command safety classification verification

## Cost Impact
- **$0 Total Cost**: No paid cloud, paid AI APIs, or SaaS tools required.

## Risk
- **Low** (Purely read-only diagnostic knowledge layer).

## Timeline
Created:
{format_pht_timestamp(created_at)}

Last updated:
{format_pht_timestamp(now)}
"""
    return preview_md

def main():
    preview = generate_release_preview()
    print(preview)
    
    out_file = Path("RELEASE_PREVIEW.md")
    out_file.write_text(preview, encoding="utf-8")
    print(f"\nGenerated Release Preview saved to {out_file.resolve()}")

if __name__ == "__main__":
    main()
