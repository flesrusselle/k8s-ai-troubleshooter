# Tiered Memory Management Protocol

Memory is a cache, not the source of truth. Current live state and source code always take precedence.

## Progressive Loading
1. Start with `AGENTS.md` and the relevant project documentation.
2. Load only the specific `README.md`, `docs/`, runbook, schema, or test file needed.
3. Then read specific source files.

## Environment Mapping
Never infer environments from namespace alone. Consult the relevant repository documentation and runbooks for environment-specific behavior.

## Memory Maintenance
Update `README.md` or the relevant `docs/` file only with stable, reusable facts. Do not store command output, credentials, or task history in repository guidance.
**DO NOT** store temporary command outputs, task history, or stories.
