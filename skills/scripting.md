# Scripting & Automation

## Tool Selection: Bash vs. Python
* **Bash:** Prefer for simple command orchestration, simple loops, file operations, and CLI pipelines (`jq`, `yq`, `gh`, `kubectl`). Always use `set -euo pipefail`.
* **Python:** Use when logic involves complex data structures, API clients, concurrency, or extensive error handling. Do not use Python for a simple command sequence.

## Idempotency & Reversibility
* Automation MUST be safe to run more than once. `Run -> desired state`, `Run again -> no unintended change`.
* Avoid scripts that append duplicate entries or fail if the desired state already exists.
* Document any operation that cannot be safely repeated.

## Troubleshooting Execution
* **Retries:** Retry ONLY transient failures. Use bounded retries or condition-based waits instead of arbitrary `sleep 30`.
* **Idempotent fixes:** Do not repeat the exact same failed fix.
