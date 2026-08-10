import datetime
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import generate_release_preview as grp
from generate_release_preview import (
    assess_risk,
    format_pht_timestamp,
    generate_release_preview,
    group_by_section,
    section_for,
    summarize,
)


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


class TestReleasePreview(unittest.TestCase):
    def test_pht_timestamp_format(self):
        dt = datetime.datetime(2026, 8, 9, 21, 30, 0, tzinfo=datetime.timezone.utc)
        formatted = format_pht_timestamp(dt)
        self.assertIn("PHT", formatted)
        self.assertIn("2026", formatted)

    def test_generate_release_preview(self):
        md = generate_release_preview()
        self.assertIn("# 🚀 Release Preview", md)
        self.assertIn("PHT", md)
        self.assertIn("## Security", md)


class TestSectionRouting(unittest.TestCase):
    def test_section_for_known_prefixes(self):
        self.assertEqual(section_for("runbooks/pods/oomkilled.md"), "Runbooks")
        self.assertEqual(section_for("decision-trees/pod-failure.yaml"), "Decision Trees")
        self.assertEqual(section_for("commands/kubectl.yaml"), "Commands")
        self.assertEqual(section_for("scripts/safety.py"), "Tooling")
        self.assertEqual(section_for(".github/workflows/ci.yml"), "CI")

    def test_section_for_unknown_path_falls_back(self):
        self.assertEqual(section_for("README.md"), "Repository")

    def test_group_by_section_follows_declared_order(self):
        changes = {
            "added": ["README.md", "runbooks/pods/new.md"],
            "modified": ["commands/kubectl.yaml"],
            "deleted": [],
        }
        self.assertEqual(
            list(group_by_section(changes)), ["Runbooks", "Commands", "Repository"]
        )


class TestSummary(unittest.TestCase):
    EMPTY = {"added": [], "modified": [], "deleted": []}

    def test_no_changes_is_stated_plainly(self):
        self.assertIn("No file changes", summarize(self.EMPTY, "main", []))

    def test_summary_reports_real_counts_not_initial_release(self):
        changes = {"added": ["a.md"], "modified": ["b.md", "c.md"], "deleted": []}
        text = summarize(changes, "main", ["fix: something"])
        self.assertIn("3 files changed", text)
        self.assertIn("1 added", text)
        self.assertIn("2 modified", text)
        self.assertIn("fix: something", text)
        self.assertNotIn("Initial release", text)

    def test_singular_file_wording(self):
        changes = {"added": [], "modified": ["b.md"], "deleted": []}
        self.assertIn("1 file changed", summarize(changes, "main", []))

    def test_initial_release_only_when_there_is_no_base(self):
        changes = {"added": ["a.md"], "modified": [], "deleted": []}
        self.assertIn("Initial release", summarize(changes, None, []))


class TestRiskAssessment(unittest.TestCase):
    def test_docs_only_change_is_low_risk(self):
        changes = {"added": [], "modified": ["docs/COST.md"], "deleted": []}
        self.assertIn("Low", assess_risk(changes))

    def test_command_catalog_change_demands_review(self):
        changes = {"added": [], "modified": ["commands/kubectl.yaml"], "deleted": []}
        risk = assess_risk(changes)
        self.assertIn("Review required", risk)
        self.assertIn("commands/kubectl.yaml", risk)

    def test_safety_module_change_demands_review(self):
        changes = {"added": ["scripts/safety.py"], "modified": [], "deleted": []}
        self.assertIn("Review required", assess_risk(changes))


class TestDiffAwareness(unittest.TestCase):
    """
    The generator used to read `git status`, which is empty in CI, and then fall
    back to listing every file under runbooks/ as "added" — so every PR claimed
    to be the initial release. These tests pin the diff to a real repository.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self._original_root = grp.REPO_ROOT
        grp.REPO_ROOT = self.repo

        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")

        (self.repo / "runbooks").mkdir()
        (self.repo / "scripts").mkdir()
        (self.repo / "runbooks" / "existing.md").write_text("original\n")
        (self.repo / "README.md").write_text("readme\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "initial")

    def tearDown(self):
        grp.REPO_ROOT = self._original_root
        self._tmp.cleanup()

    def _branch_with_changes(self):
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "scripts" / "safety.py").write_text("new module\n")
        (self.repo / "runbooks" / "existing.md").write_text("changed\n")
        (self.repo / "README.md").unlink()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "fix: rework safety")

    def test_changed_files_are_classified_by_status(self):
        self._branch_with_changes()
        base_label, base_sha = grp.resolve_base()
        self.assertEqual(base_label, "main")

        changes = grp.get_changed_files(base_sha)
        self.assertEqual(changes["added"], ["scripts/safety.py"])
        self.assertEqual(changes["modified"], ["runbooks/existing.md"])
        self.assertEqual(changes["deleted"], ["README.md"])

    def test_untouched_files_are_not_reported(self):
        self._branch_with_changes()
        (self.repo / "runbooks" / "untouched.md").write_text("x\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "add untouched")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "checkout", "-q", "feature")

        _, base_sha = grp.resolve_base()
        changes = grp.get_changed_files(base_sha)
        every_path = changes["added"] + changes["modified"] + changes["deleted"]
        self.assertNotIn("runbooks/other.md", every_path)

    def test_preview_does_not_claim_initial_release_on_a_branch(self):
        self._branch_with_changes()
        md = generate_release_preview()
        self.assertNotIn("Initial release", md)
        self.assertIn("fix: rework safety", md)
        self.assertIn("`scripts/safety.py` — added", md)
        self.assertIn("`README.md` — removed", md)
        self.assertIn("Review required", md)

    def test_renamed_file_reports_new_path_once(self):
        git(self.repo, "checkout", "-q", "-b", "rename")
        git(self.repo, "mv", "runbooks/existing.md", "runbooks/renamed.md")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "docs: rename runbook")

        _, base_sha = grp.resolve_base()
        changes = grp.get_changed_files(base_sha)
        self.assertIn("runbooks/renamed.md", changes["modified"])
        self.assertNotIn("runbooks/existing.md", changes["modified"])

    def test_base_branch_falls_back_to_last_commit(self):
        (self.repo / "runbooks" / "second.md").write_text("second\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "feat: second runbook")

        base_label, base_sha = grp.resolve_base()
        self.assertEqual(base_label, "HEAD~1")
        changes = grp.get_changed_files(base_sha)
        self.assertEqual(changes["added"], ["runbooks/second.md"])


if __name__ == "__main__":
    unittest.main()
