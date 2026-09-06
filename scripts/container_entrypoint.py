#!/usr/bin/env python3
"""Configure kubectl for in-cluster execution without persisting credentials."""

import os
import sys
from pathlib import Path

SERVICE_ACCOUNT_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
TEMP_KUBECONFIG = Path("/tmp/kubeconfig")


def configure_in_cluster_kubeconfig():
    """Create a temporary kubeconfig only when Kubernetes mounted a token."""
    if os.environ.get("KUBECONFIG"):
        return

    token_path = SERVICE_ACCOUNT_DIR / "token"
    ca_path = SERVICE_ACCOUNT_DIR / "ca.crt"
    host = os.environ.get("KUBERNETES_SERVICE_HOST")
    port = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
    if not host or not token_path.exists() or not ca_path.exists():
        return

    token = token_path.read_text(encoding="utf-8").strip()
    kubeconfig = f"""apiVersion: v1
kind: Config
clusters:
- name: in-cluster
  cluster:
    server: https://{host}:{port}
    certificate-authority: {ca_path}
users:
- name: in-cluster
  user:
    token: {token}
contexts:
- name: in-cluster
  context:
    cluster: in-cluster
    user: in-cluster
current-context: in-cluster
"""
    TEMP_KUBECONFIG.write_text(kubeconfig, encoding="utf-8")
    TEMP_KUBECONFIG.chmod(0o600)
    os.environ["KUBECONFIG"] = str(TEMP_KUBECONFIG)


def main():
    configure_in_cluster_kubeconfig()
    os.execvp("python3", ["python3", "scripts/k8s_ai.py", *sys.argv[1:]])


if __name__ == "__main__":
    main()
