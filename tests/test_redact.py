import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from redact import REDACTION_MARKER, fingerprint, redact


def is_redacted(text, secret):
    """The secret is gone and a marker took its place."""
    return secret not in text and REDACTION_MARKER in text


class TestHighConfidencePatterns(unittest.TestCase):
    def test_jwt_is_redacted(self):
        secret = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r"
        out, stats = redact(f"token={secret}")
        self.assertTrue(is_redacted(out, secret))
        self.assertEqual(stats.get("jwt"), 1)

    def test_aws_access_key_is_redacted(self):
        secret = "AKIAIOSFODNN7EXAMPLE"
        out, _ = redact(f"AWS_ACCESS_KEY_ID: {secret}")
        self.assertTrue(is_redacted(out, secret))

    def test_github_token_is_redacted(self):
        secret = "ghp_" + "a" * 36
        out, _ = redact(f"pushing with {secret}")
        self.assertTrue(is_redacted(out, secret))

    def test_private_key_block_is_redacted(self):
        secret = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQ\nnope\n-----END RSA PRIVATE KEY-----"
        out, _ = redact(f"tls.key: |\n{secret}\n")
        self.assertNotIn("MIIEowIBAAKCAQ", out)
        self.assertIn(REDACTION_MARKER, out)

    def test_url_credentials_are_redacted_but_host_survives(self):
        out, _ = redact("DSN=postgres://app:s3cr3t@db.prod.svc:5432/main")
        self.assertNotIn("s3cr3t", out)
        # The parts you actually need for diagnosis are preserved.
        self.assertIn("db.prod.svc:5432/main", out)
        self.assertIn("app", out)

    def test_bearer_token_in_log_line_is_redacted(self):
        out, _ = redact("GET /v1 401 Authorization: Bearer abcdef0123456789ABCDEF")
        self.assertNotIn("abcdef0123456789ABCDEF", out)


class TestKeyNameHeuristics(unittest.TestCase):
    def test_sensitive_yaml_key_is_redacted(self):
        out, _ = redact("      DB_PASSWORD:    hunter2")
        self.assertTrue(is_redacted(out, "hunter2"))

    def test_sensitive_env_assignment_is_redacted(self):
        out, _ = redact("starting with API_TOKEN=abc123 and mode=fast")
        self.assertNotIn("abc123", out)
        self.assertIn("mode=fast", out)

    def test_sensitive_json_key_is_redacted(self):
        out, _ = redact('{"client_secret": "abc123xyz", "region": "us-east-1"}')
        self.assertNotIn("abc123xyz", out)
        self.assertIn("us-east-1", out)

    def test_harmless_values_are_preserved(self):
        """Over-redaction has a real cost: it destroys the diagnosis."""
        text = "LOG_LEVEL: debug\nREPLICA_COUNT: 3\nIMAGE: nginx:1.25\nExit Code: 137"
        out, _ = redact(text)
        self.assertEqual(out, text)

    def test_allowlisted_keys_are_not_redacted(self):
        """These name a secret without containing one, and are load-bearing."""
        text = "secretName: tls-cert\nserviceAccountName: my-sa"
        out, _ = redact(text)
        self.assertIn("tls-cert", out)
        self.assertIn("my-sa", out)


class TestSecretManifests(unittest.TestCase):
    def test_secret_data_block_is_redacted_regardless_of_key_name(self):
        """
        `kubectl get secret -o yaml` uses arbitrary filenames as keys, so no
        key-name heuristic can catch them. The block itself is the signal.
        """
        text = "kind: Secret\ndata:\n  ca.crt: LS0tQ0VSVA==\n  config.json: eyJhIjoxfQ==\n"
        out, stats = redact(text)
        self.assertNotIn("LS0tQ0VSVA==", out)
        self.assertNotIn("eyJhIjoxfQ==", out)
        self.assertEqual(stats.get("secret-data"), 2)

    def test_string_data_block_is_redacted(self):
        out, _ = redact("stringData:\n  anything: correct-horse\n")
        self.assertNotIn("correct-horse", out)

    def test_keys_after_the_data_block_are_not_swept_up(self):
        """Leaving the block must reset, or unrelated fields get destroyed."""
        text = (
            "data:\n"
            "  token: c2VjcmV0\n"
            "metadata:\n"
            "  name: my-secret\n"
            "  namespace: prod\n"
        )
        out, _ = redact(text)
        self.assertNotIn("c2VjcmV0", out)
        self.assertIn("my-secret", out)
        self.assertIn("prod", out)


class TestFingerprints(unittest.TestCase):
    def test_identical_secrets_share_a_fingerprint(self):
        """This is what lets you correlate a secret across files without seeing it."""
        out, _ = redact("A_TOKEN: samevalue\nB_PASSWORD: samevalue\n")
        self.assertIn(fingerprint("samevalue"), out)
        self.assertEqual(out.count(fingerprint("samevalue")), 2)

    def test_different_secrets_get_different_fingerprints(self):
        out, _ = redact("A_TOKEN: one\nB_TOKEN: two\n")
        self.assertIn(fingerprint("one"), out)
        self.assertIn(fingerprint("two"), out)
        self.assertNotEqual(fingerprint("one"), fingerprint("two"))

    def test_fingerprint_does_not_leak_the_value(self):
        secret = "hunter2"
        out, _ = redact(f"PASSWORD: {secret}")
        self.assertNotIn(secret, out)


class TestIdempotence(unittest.TestCase):
    def test_redacting_twice_changes_nothing(self):
        text = "DB_PASSWORD: hunter2\nDSN=postgres://u:p@host/db\n"
        once, _ = redact(text)
        twice, stats = redact(once)
        self.assertEqual(once, twice)
        self.assertEqual(stats, {})

    def test_empty_input_is_safe(self):
        out, stats = redact("")
        self.assertEqual(out, "")
        self.assertEqual(stats, {})


if __name__ == "__main__":
    unittest.main()
