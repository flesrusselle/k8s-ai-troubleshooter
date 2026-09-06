import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import container_entrypoint


class TestContainerEntrypoint(unittest.TestCase):
    def test_explicit_kubeconfig_is_preserved(self):
        with patch.dict(os.environ, {"KUBECONFIG": "/tmp/external-kubeconfig"}, clear=False):
            container_entrypoint.configure_in_cluster_kubeconfig()
            self.assertEqual("/tmp/external-kubeconfig", os.environ["KUBECONFIG"])

    def test_in_cluster_kubeconfig_uses_mounted_token_and_ca(self):
        with tempfile.TemporaryDirectory() as directory:
            service_account = Path(directory)
            token = service_account / "token"
            ca = service_account / "ca.crt"
            token.write_text("token-value\n", encoding="utf-8")
            ca.write_text("certificate", encoding="utf-8")
            with patch.object(container_entrypoint, "SERVICE_ACCOUNT_DIR", service_account), \
                    patch.object(container_entrypoint, "TEMP_KUBECONFIG", service_account / "kubeconfig"), \
                    patch.dict(os.environ, {
                        "KUBERNETES_SERVICE_HOST": "10.0.0.1",
                        "KUBERNETES_SERVICE_PORT_HTTPS": "443",
                    }, clear=True):
                container_entrypoint.configure_in_cluster_kubeconfig()
                content = (service_account / "kubeconfig").read_text(encoding="utf-8")
                configured_path = os.environ["KUBECONFIG"]

        self.assertIn("server: https://10.0.0.1:443", content)
        self.assertIn("token: token-value", content)
        self.assertTrue(configured_path.endswith("/kubeconfig"))


if __name__ == "__main__":
    unittest.main()
