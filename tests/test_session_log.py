import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import session_log


class TestLogPathResolution(unittest.TestCase):
    def test_default_path_is_relative_and_hidden(self):
        original = __import__("os").environ.pop("K8S_AI_TROUBLESHOOTER_SESSION_LOG", None)
        try:
            self.assertEqual(session_log.log_path(), Path(".k8s-ai-troubleshooter") / "sessions.jsonl")
        finally:
            if original is not None:
                __import__("os").environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = original

    def test_env_var_overrides_the_default(self):
        import os

        original = os.environ.get("K8S_AI_TROUBLESHOOTER_SESSION_LOG")
        os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = "/tmp/shared-team-log.jsonl"
        try:
            self.assertEqual(session_log.log_path(), Path("/tmp/shared-team-log.jsonl"))
        finally:
            if original is None:
                del os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"]
            else:
                os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = original


class TestRecordAndRead(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_file = Path(self._tmp.name) / "nested" / "sessions.jsonl"
        import os
        self._original_env = os.environ.get("K8S_AI_TROUBLESHOOTER_SESSION_LOG")
        os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = str(self.log_file)

    def tearDown(self):
        import os
        if self._original_env is None:
            os.environ.pop("K8S_AI_TROUBLESHOOTER_SESSION_LOG", None)
        else:
            os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = self._original_env
        self._tmp.cleanup()

    def test_record_creates_parent_directories(self):
        self.assertFalse(self.log_file.parent.exists())
        session_log.record("collect", scope="prod")
        self.assertTrue(self.log_file.exists())

    def test_record_returns_and_persists_the_same_entry(self):
        entry = session_log.record("mcp", signal="CrashLoopBackOff", confidence="High")
        stored = session_log.read_entries()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["session_id"], entry["session_id"])
        self.assertEqual(stored[0]["confidence"], "High")

    def test_every_entry_gets_a_unique_session_id_and_timestamp(self):
        first = session_log.record("collect")
        second = session_log.record("collect")
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertIn("timestamp", first)

    def test_none_fields_are_omitted_not_written_as_null(self):
        """A log full of nulls is unpleasant to grep; omit what wasn't given."""
        session_log.record("mcp", signal="x", root_cause=None, notes=None)
        raw_line = self.log_file.read_text(encoding="utf-8").strip()
        self.assertNotIn("null", raw_line)
        self.assertNotIn("root_cause", raw_line)

    def test_entries_are_appended_not_overwritten(self):
        session_log.record("collect", scope="a")
        session_log.record("collect", scope="b")
        session_log.record("collect", scope="c")
        self.assertEqual(len(session_log.read_entries()), 3)

    def test_reading_a_missing_log_returns_empty_not_an_error(self):
        self.assertEqual(session_log.read_entries(Path("/tmp/definitely-does-not-exist-12345.jsonl")), [])

    def test_a_corrupted_line_is_skipped_not_fatal(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "w", encoding="utf-8") as handle:
            handle.write("not valid json\n")
            handle.write(json.dumps({"session_id": "ok-1", "source": "collect"}) + "\n")
        entries = session_log.read_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["session_id"], "ok-1")

    def test_blank_lines_are_ignored(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "w", encoding="utf-8") as handle:
            handle.write("\n\n")
            handle.write(json.dumps({"session_id": "ok-1", "source": "collect"}) + "\n")
        self.assertEqual(len(session_log.read_entries()), 1)


class TestSummarize(unittest.TestCase):
    def test_empty_log_says_so_plainly(self):
        self.assertIn("No sessions", session_log.summarize([]))

    def test_counts_by_runbook_confidence_and_source(self):
        entries = [
            {"runbook": "runbooks/pods/oomkilled.md", "confidence": "High", "source": "mcp"},
            {"runbook": "runbooks/pods/oomkilled.md", "confidence": "Medium", "source": "mcp"},
            {"runbook": "runbooks/pods/crashloopbackoff.md", "confidence": "High", "source": "collect"},
        ]
        summary = session_log.summarize(entries)
        self.assertIn("3 session(s)", summary)
        self.assertIn("runbooks/pods/oomkilled.md", summary)
        self.assertIn("High", summary)
        self.assertIn("mcp", summary)

    def test_recurring_runbook_is_flagged_at_three_occurrences(self):
        entries = [{"runbook": "runbooks/pods/oomkilled.md"} for _ in range(3)]
        summary = session_log.summarize(entries)
        self.assertIn("Recurring", summary)
        self.assertIn("runbooks/pods/oomkilled.md", summary.split("Recurring")[1])

    def test_two_occurrences_are_not_flagged_as_recurring(self):
        entries = [{"runbook": "runbooks/pods/oomkilled.md"} for _ in range(2)]
        self.assertNotIn("Recurring", session_log.summarize(entries))

    def test_unrouted_entries_are_labelled_but_never_flagged_recurring(self):
        entries = [{} for _ in range(5)]  # no "runbook" key at all
        summary = session_log.summarize(entries)
        self.assertIn("(unrouted)", summary)
        self.assertNotIn("Recurring", summary)

    def test_missing_confidence_is_labelled_not_silently_dropped(self):
        summary = session_log.summarize([{"runbook": "x"}])
        self.assertIn("(not stated)", summary)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_file = Path(self._tmp.name) / "sessions.jsonl"
        import os
        self._original_env = os.environ.get("K8S_AI_TROUBLESHOOTER_SESSION_LOG")
        os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = str(self.log_file)
        session_log.record("collect", scope="prod")
        session_log.record("mcp", runbook="runbooks/pods/oomkilled.md", confidence="High")

    def tearDown(self):
        import os
        if self._original_env is None:
            os.environ.pop("K8S_AI_TROUBLESHOOTER_SESSION_LOG", None)
        else:
            os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = self._original_env
        self._tmp.cleanup()

    def test_path_flag_prints_resolved_path_and_exits_zero(self):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = session_log.main(["--path"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), str(self.log_file))

    def test_tail_flag_prints_valid_json_lines(self):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            session_log.main(["--tail", "1"])
        lines = [line for line in buf.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        json.loads(lines[0])  # must not raise

    def test_default_invocation_prints_a_summary(self):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            session_log.main([])
        self.assertIn("2 session(s)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
