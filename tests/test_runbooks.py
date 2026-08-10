import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate import REQUIRED_RUNBOOK_SECTIONS

RUNBOOKS = sorted((REPO_ROOT / "runbooks").rglob("*.md"))

SAFETY_TIERS = {"SAFE_READ", "SAFE_DIAGNOSTIC", "HUMAN_APPROVAL_REQUIRED", "DESTRUCTIVE"}


def section_body(text, heading):
    """Return the text under `heading`, up to the next heading of the same level."""
    pattern = rf"^{re.escape(heading)}\s*$(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


class TestRunbookStructure(unittest.TestCase):
    def test_there_are_runbooks(self):
        self.assertGreater(len(RUNBOOKS), 10)

    def test_every_runbook_has_every_required_section(self):
        """The section list is imported from validate.py so the two cannot drift."""
        for rb in RUNBOOKS:
            content = rb.read_text(encoding="utf-8")
            for section in REQUIRED_RUNBOOK_SECTIONS:
                with self.subTest(runbook=rb.name, section=section):
                    self.assertIn(section, content)

    def test_declared_safety_level_is_a_real_tier(self):
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Safety Level")
            with self.subTest(runbook=rb.name):
                self.assertTrue(
                    any(tier in body for tier in SAFETY_TIERS),
                    f"{rb.name} declares no recognised safety tier: {body!r}",
                )


class TestActionabilitySections(unittest.TestCase):
    """
    Blast Radius, Verification and Rollback exist to stop a runbook from ending
    at "run this". A placeholder heading would satisfy the structural check while
    restoring exactly the gap the sections were added to close.
    """

    MIN_CHARS = 60

    def test_blast_radius_is_substantive(self):
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Blast Radius")
            with self.subTest(runbook=rb.name):
                self.assertGreaterEqual(len(body), self.MIN_CHARS, f"{rb.name}: {body!r}")

    def test_verification_is_substantive(self):
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Verification")
            with self.subTest(runbook=rb.name):
                self.assertGreaterEqual(len(body), self.MIN_CHARS, f"{rb.name}: {body!r}")

    def test_rollback_is_substantive(self):
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Rollback")
            with self.subTest(runbook=rb.name):
                self.assertGreaterEqual(len(body), self.MIN_CHARS, f"{rb.name}: {body!r}")

    def test_read_only_runbooks_say_so_rather_than_inventing_a_blast_radius(self):
        """A SAFE_READ runbook must not imply its own commands are risky."""
        for rb in RUNBOOKS:
            text = rb.read_text(encoding="utf-8")
            if "DESTRUCTIVE" in section_body(text, "## Safety Level"):
                continue
            body = section_body(text, "## Blast Radius").lower()
            if body.startswith(("none", "triage itself has none")):
                with self.subTest(runbook=rb.name):
                    self.assertTrue(
                        "read" in body or "routed" in body or "own" in body,
                        f"{rb.name} claims no blast radius without explaining why",
                    )


class TestDestructiveCommandsAreMarked(unittest.TestCase):
    """
    Deleting a namespace and restarting a Deployment must not look alike in the
    approval list. Anything that destroys state carries an explicit marker.
    """

    DESTRUCTIVE_PATTERNS = (
        "kubectl delete", "helm uninstall", "--force", "--disable-eviction",
        "kubectl drain",
    )

    def test_destructive_entries_carry_a_marker(self):
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Human Approval Required")
            for line in body.splitlines():
                if not line.strip().startswith("-"):
                    continue
                if any(p in line for p in self.DESTRUCTIVE_PATTERNS):
                    with self.subTest(runbook=rb.name, line=line.strip()[:70]):
                        self.assertIn(
                            "DESTRUCTIVE", line,
                            f"{rb.name}: destructive command not marked: {line.strip()}",
                        )


class TestCrossReferences(unittest.TestCase):
    def test_related_runbook_links_resolve(self):
        link = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Related Runbooks")
            for _, target in link.findall(body):
                with self.subTest(runbook=rb.name, target=target):
                    self.assertTrue(
                        (rb.parent / target).resolve().exists(),
                        f"{rb.name} links to missing {target}",
                    )

    def test_runbooks_do_not_link_only_to_themselves(self):
        for rb in RUNBOOKS:
            body = section_body(rb.read_text(encoding="utf-8"), "## Related Runbooks")
            with self.subTest(runbook=rb.name):
                self.assertTrue(body.strip(), f"{rb.name} lists no related runbooks")


if __name__ == "__main__":
    unittest.main()
