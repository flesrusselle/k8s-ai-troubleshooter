# MCP (Model Context Protocol) Server Integration

`k8s-ai-troubleshooter` provides an optional, local-first MCP server adapter allowing MCP-compatible AI clients (e.g. Claude Desktop, Cursor, Antigravity) to query runbooks, decision trees, and command safety classifications via standard MCP tools.

---

## 🏗️ Architecture

```text
Runbooks & Decision Trees (Repository Files)
              │
              ▼
    integrations/mcp/server.py (Local Python MCP Server)
              │
              ▼
   MCP Client (Claude Desktop / Cursor / Antigravity)
```

The server reads directly from the canonical repository files (`runbooks/`, `decision-trees/`, `commands/`).

---

## ⚡ Running the MCP Server

```bash
# Run locally using standard Python 3
python3 integrations/mcp/server.py
```

### Exposed MCP Tools

1. `list_runbooks`: Returns available diagnostic runbooks.
2. `get_runbook`: Reads runbook content by ID.
3. `query_command_safety`: Evaluates the safety classification of a `kubectl` or `helm` command.
4. `get_decision_tree`: Returns a structured decision tree YAML.
