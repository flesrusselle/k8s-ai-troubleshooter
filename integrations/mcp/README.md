# MCP (Model Context Protocol) Server

A local-first MCP server exposing this repository's diagnostic knowledge as
callable tools, for MCP-compatible clients such as Claude Code, Claude Desktop,
Cursor and Antigravity.

**Full setup instructions, client configs and a worked exchange:
[docs/usage/mcp.md](../../docs/usage/mcp.md).**

---

## Architecture

```text
runbooks/  decision-trees/  commands/  symptom-index.yaml
                        │
                        ▼
        integrations/mcp/server.py  (JSON-RPC 2.0 over stdio)
                        │
                        ▼
     MCP client (Claude Code / Claude Desktop / Cursor / Antigravity)
```

The server reads the canonical repository files directly. It has **no cluster
access and no credentials** — it serves knowledge, and command execution stays
with the client under the client's own permission model.

Standard library only, apart from `pyyaml` for symptom routing.

---

## Exposed tools

| Tool | Arguments | Returns |
| :--- | :--- | :--- |
| `list_runbooks` | — | All runbooks with id, category, path |
| `get_runbook` | `runbook_id` | Full runbook text |
| `get_decision_tree` | `tree_id` | Decision tree YAML |
| `query_command_safety` | `command` | Safety tier, reason, whether auto-execution is allowed |
| `route_symptom` | `signal` | Runbooks matching an observed signal, ranked by specificity |

---

## Running it

The server speaks **stdio**: it reads JSON-RPC requests on stdin and writes
responses on stdout. Launching it in a terminal with no client attached will
appear to hang — that is it waiting for input, and is correct.

```bash
# Health check
python3 integrations/mcp/server.py --test

# Classify a command without a client
python3 integrations/mcp/server.py --classify "kubectl delete ns prod"

# Route a symptom without a client
python3 integrations/mcp/server.py --route "137"

# Speak the protocol by hand
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python3 integrations/mcp/server.py
```

Implemented methods: `initialize`, `tools/list`, `tools/call`, `ping`. The
`protocolVersion` a client requests is echoed back, so the server keeps working
as the specification revises.

---

## Client configuration

Absolute paths are required — the server is launched without a shell, so `~`
and relative paths do not resolve.

```json
{
  "mcpServers": {
    "k8s-troubleshooter": {
      "command": "python3",
      "args": ["/absolute/path/to/k8s-ai-troubleshooter/integrations/mcp/server.py"]
    }
  }
}
```

See [docs/usage/mcp.md](../../docs/usage/mcp.md) for per-client file locations.
