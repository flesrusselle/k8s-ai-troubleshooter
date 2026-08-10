import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "symptom-index.yaml"


def load_index():
    return yaml.safe_load(INDEX_PATH.read_text(encoding="utf-8"))


class TestSymptomIndexIntegrity(unittest.TestCase):
    """
    The index is the routing table an assistant uses to pick a runbook. A stale
    entry sends the investigation to a file that does not exist; an unrouted
    runbook is one nothing will ever open.
    """

    @classmethod
    def setUpClass(cls):
        cls.index = load_index()
        cls.entries = cls.index["entries"]

    def test_entry_ids_are_unique(self):
        ids = [entry["id"] for entry in self.entries]
        duplicates = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(duplicates, set(), f"duplicate entry ids: {duplicates}")

    def test_every_entry_routes_to_an_existing_runbook(self):
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                self.assertTrue(
                    (REPO_ROOT / entry["runbook"]).exists(),
                    f"{entry['id']} routes to missing runbook {entry['runbook']}",
                )

    def test_every_referenced_decision_tree_exists(self):
        for entry in self.entries:
            tree = entry.get("decision_tree")
            if tree:
                with self.subTest(entry=entry["id"]):
                    self.assertTrue((REPO_ROOT / tree).exists(), f"missing tree {tree}")

    def test_every_runbook_is_reachable(self):
        """A runbook nothing routes to is dead weight."""
        routed = {entry["runbook"] for entry in self.entries}
        routed.add(self.index["default_entry"])
        on_disk = {
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "runbooks").rglob("*.md")
        }
        self.assertEqual(
            on_disk - routed, set(),
            "these runbooks are unreachable from symptom-index.yaml",
        )

    def test_default_entry_exists(self):
        self.assertTrue((REPO_ROOT / self.index["default_entry"]).exists())

    def test_every_entry_declares_at_least_one_signal(self):
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                signals = entry.get("signals", {})
                self.assertTrue(signals, f"{entry['id']} declares no signals")
                self.assertTrue(
                    any(values for values in signals.values()),
                    f"{entry['id']} has only empty signal lists",
                )

    def test_signal_types_are_declared(self):
        """An undeclared signal type means the assistant cannot know where to look."""
        declared = set(self.index["signal_types"])
        for entry in self.entries:
            for signal_type in entry.get("signals", {}):
                with self.subTest(entry=entry["id"], signal=signal_type):
                    self.assertIn(signal_type, declared)

    def test_every_entry_offers_a_first_command(self):
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                self.assertTrue(entry.get("first_command", "").strip())

    def test_first_commands_are_read_only(self):
        """Routing must never suggest a mutation as the opening move."""
        import sys

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from safety import SAFE_DIAGNOSTIC, SAFE_READ, classify

        for entry in self.entries:
            command = entry["first_command"]
            # Placeholders are not valid shell; classify the shape, not the value.
            concrete = (
                command.replace("<pod>", "web-1").replace("<namespace>", "prod")
                .replace("<service>", "api").replace("<node>", "node-1")
                .replace("<name>", "api").replace("<claim>", "data")
                .replace("<ingress>", "web").replace("<resource>", "deployment")
            )
            with self.subTest(entry=entry["id"]):
                self.assertIn(
                    classify(concrete).safety, {SAFE_READ, SAFE_DIAGNOSTIC},
                    f"{entry['id']} opens with a non-read-only command: {concrete}",
                )


class TestCriticalSignalsAreRouted(unittest.TestCase):
    """
    Regression guard: these are the states an operator is most likely to arrive
    with. If any stops resolving, routing has silently regressed.
    """

    @classmethod
    def setUpClass(cls):
        cls.index = load_index()

    def _lookup(self, needle):
        for entry in self.index["entries"]:
            for values in entry.get("signals", {}).values():
                if needle in [str(v) for v in values]:
                    return entry
        return None

    def test_common_states_resolve(self):
        for signal in [
            "CrashLoopBackOff", "OOMKilled", "ImagePullBackOff", "ErrImagePull",
            "Pending", "Evicted", "FailedScheduling", "FailedMount",
            "ProvisioningFailed", "Unhealthy", "137",
        ]:
            with self.subTest(signal=signal):
                entry = self._lookup(signal)
                self.assertIsNotNone(entry, f"no runbook routes signal {signal!r}")

    def test_exit_code_137_routes_to_oomkilled(self):
        """137 is SIGKILL, which in practice means the OOM killer."""
        self.assertEqual(self._lookup("137")["runbook"], "runbooks/pods/oomkilled.md")


if __name__ == "__main__":
    unittest.main()
