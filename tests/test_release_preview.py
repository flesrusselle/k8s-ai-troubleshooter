import datetime
import unittest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_release_preview import format_pht_timestamp, generate_release_preview

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

if __name__ == "__main__":
    unittest.main()
