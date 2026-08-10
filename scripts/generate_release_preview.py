#!/usr/bin/env python3
"""
PR Release Preview Generator for k8s-ai-troubleshooter

Generates structured Release Preview markdown describing what a change set
actually does, derived from the Git diff between the base branch and HEAD.
Formatted using Asia/Manila (PHT) timestamps.

Resolution order for the base ref:

1. $RELEASE_PREVIEW_BASE, for local overrides;
2. $GITHUB_BASE_REF, set by GitHub Actions on pull_request events;
3. origin/main, main, origin/master, master.

The diff is taken from the merge base, so commits landing on the base branch
after this one branched off are not reported as part of this change set. When
HEAD *is* the base branch (a push to main), the preview falls back to the last
commit, and when the repository has no parent commit at all it reports an
initial release.
"""

import datetime
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Try timezone import or fallback
try:
    import zoneinfo
    PHT_TZ = zoneinfo.ZoneInfo("Asia/Manila")
except Exception:
    # Standard UTC+8 offset fallback for Asia/Manila
    PHT_TZ = datetime.timezone(datetime.timedelta(hours=8))

# Top-level path prefix -> release preview section, most specific first.
SECTIONS = [
    ("runbooks/", "Runbooks"),
    ("decision-trees/", "Decision Trees"),
    ("commands/", "Commands"),
    ("integrations/", "AI Integrations"),
    ("schemas/", "Schemas"),
    ("scripts/", "Tooling"),
    ("tests/", "Tests"),
    ("docs/", "Documentation"),
    (".github/", "CI"),
]
OTHER_SECTION = "Repository"

# Paths where a change alters what the engine will let an operator run.
SAFETY_CRITICAL = ("commands/", "scripts/safety.py", "integrations/")


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


def _git(*args):
    """Run a git command, returning stripped stdout or None if it failed."""
    try:
        res = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return res.stdout.strip()


def _ref_exists(ref):
    return bool(_git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"))


def resolve_base():
    """
    Return (base_label, base_sha) to diff HEAD against, or (None, None).

    base_label is what a human should see; base_sha is what git should diff.
    """
    candidates = []
    for env_var in ("RELEASE_PREVIEW_BASE", "GITHUB_BASE_REF"):
        branch = os.environ.get(env_var)
        if branch:
            candidates.extend([f"origin/{branch}", branch])
    candidates.extend(["origin/main", "main", "origin/master", "master"])

    head = _git("rev-parse", "HEAD")
    seen = set()
    for ref in candidates:
        if ref in seen or not _ref_exists(ref):
            continue
        seen.add(ref)
        merge_base = _git("merge-base", ref, "HEAD")
        if not merge_base:
            continue
        # HEAD is the base branch itself: preview the last commit instead.
        if merge_base == head:
            continue
        return ref, merge_base

    parent = _git("rev-parse", "--verify", "--quiet", "HEAD~1")
    if parent:
        return "HEAD~1", parent
    return None, None


def get_changed_files(base_sha):
    """
    Return {"added": [...], "modified": [...], "deleted": [...]} for base..HEAD.

    Falls back to the working tree when there is no base commit to diff against,
    so the generator stays useful outside of CI.
    """
    changes = {"added": [], "modified": [], "deleted": []}

    if base_sha:
        raw = _git("diff", "--name-status", "-M", f"{base_sha}...HEAD")
        for line in (raw or "").splitlines():
            fields = line.split("\t")
            if len(fields) < 2:
                continue
            code = fields[0][:1]
            # Renames report old and new path; the new path is what shipped.
            path = fields[-1]
            if code == "A":
                changes["added"].append(path)
            elif code == "D":
                changes["deleted"].append(path)
            else:
                # M, R, C, T all mean "this file is different now".
                changes["modified"].append(path)
        return changes

    raw = _git("status", "--porcelain", "-uall")
    for line in (raw or "").splitlines():
        if not line.strip():
            continue
        status, path = line[:2], line[3:].strip()
        if "D" in status:
            changes["deleted"].append(path)
        elif "?" in status or "A" in status:
            changes["added"].append(path)
        else:
            changes["modified"].append(path)
    return changes


def section_for(path):
    for prefix, name in SECTIONS:
        if path.startswith(prefix):
            return name
    return OTHER_SECTION


def group_by_section(changes):
    """Return {section: [(verb, path), ...]} ordered as in SECTIONS."""
    grouped = {}
    for verb in ("added", "modified", "deleted"):
        for path in sorted(changes[verb]):
            grouped.setdefault(section_for(path), []).append((verb, path))

    order = [name for _, name in SECTIONS] + [OTHER_SECTION]
    return {name: grouped[name] for name in order if name in grouped}


def summarize(changes, base_label, commits):
    """Build the Summary section body from what actually changed."""
    total = sum(len(v) for v in changes.values())
    if total == 0:
        return f"No file changes detected against `{base_label}`."

    if base_label is None:
        return (
            "Initial release of `k8s-ai-troubleshooter` — an open-source, "
            "model-agnostic, deterministic Kubernetes troubleshooting engine "
            "and diagnostic runbook system."
        )

    counts = ", ".join(
        f"{len(changes[verb])} {verb}"
        for verb in ("added", "modified", "deleted")
        if changes[verb]
    )
    plural = "file" if total == 1 else "files"
    lines = [f"{total} {plural} changed against `{base_label}` ({counts})."]

    if commits:
        lines.append("")
        lines.extend(f"- {subject}" for subject in commits)
    return "\n".join(lines)


def assess_risk(changes):
    touched = sorted(
        {
            path
            for verb in ("added", "modified", "deleted")
            for path in changes[verb]
            if path.startswith(SAFETY_CRITICAL)
        }
    )
    if not touched:
        return "- **Low** (Purely read-only diagnostic knowledge layer; no changes to command classification.)"

    listed = "\n".join(f"  - `{path}`" for path in touched)
    return (
        "- **Review required** — this change touches command classification or "
        "the adapters that consume it, which determines what an operator is "
        "allowed to run:\n" + listed
    )


def generate_release_preview(created_at: datetime.datetime = None):
    now = datetime.datetime.now(PHT_TZ)
    if created_at is None:
        created_at = now

    base_label, base_sha = resolve_base()
    changes = get_changed_files(base_sha)
    commits = []
    if base_sha:
        # --no-merges: on pull_request, Actions checks out a synthetic merge
        # commit whose subject ("Merge <sha> into <sha>") is not a change.
        raw = _git("log", "--no-merges", "--format=%s", f"{base_sha}..HEAD")
        commits = [line for line in (raw or "").splitlines() if line.strip()]

    grouped = group_by_section(changes)
    verb_marks = {"added": "added", "modified": "modified", "deleted": "removed"}

    body = [
        "# 🚀 Release Preview",
        "",
        "## Summary",
        summarize(changes, base_label, commits),
        "",
        "## Changes",
    ]

    if grouped:
        for section, entries in grouped.items():
            body.append("")
            body.append(f"### {section}")
            body.extend(f"- `{path}` — {verb_marks[verb]}" for verb, path in entries)
    else:
        body.append("")
        body.append("- No files changed.")

    body += [
        "",
        "## Security",
        "- **Strict Read-Only Default**: Zero automated state mutation allowed.",
        "- **Human Approval**: State-changing commands explicitly require human operator consent.",
        "",
        "## Testing",
        "- JSON Schema validation",
        "- Runbook section completeness check",
        "- Internal documentation link resolution",
        "- Python offline test suite (`unittest`)",
        "- Command safety classification verification",
        "",
        "## Cost Impact",
        "- **$0 Total Cost**: No paid cloud, paid AI APIs, or SaaS tools required.",
        "",
        "## Risk",
        assess_risk(changes),
        "",
        "## Timeline",
        "Created:",
        format_pht_timestamp(created_at),
        "",
        "Last updated:",
        format_pht_timestamp(now),
        "",
    ]
    return "\n".join(body)


def main():
    preview = generate_release_preview()
    print(preview)

    out_file = Path("RELEASE_PREVIEW.md")
    out_file.write_text(preview, encoding="utf-8")
    print(f"\nGenerated Release Preview saved to {out_file.resolve()}")


if __name__ == "__main__":
    main()
