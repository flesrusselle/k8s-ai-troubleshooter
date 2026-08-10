# Using `k8s-ai-troubleshooter` over MCP

The MCP server exposes this repository's knowledge as callable tools, so a
client resolves symptoms and safety tiers by **calling a function** rather than
by reading instructions and hoping they were followed.

That difference matters. A prompt saying "classify commands before running them"
is advice. A `query_command_safety` tool the model must call is a mechanism.

---

## What it exposes

| Tool | Purpose |
| :--- | :--- |
| `list_runbooks` | Every runbook with id, category, path |
| `get_runbook` | Full runbook text by id, e.g. `crashloopbackoff` |
| `get_decision_tree` | Decision tree YAML by id, e.g. `pod-failure` |
| `query_command_safety` | Safety tier + reason for any kubectl/helm command |
| `route_symptom` | Map an observed signal to the runbook that handles it |

`route_symptom` is the one that changes how a session goes. Given
`CrashLoopBackOff`, exit code `137`, or a raw log line containing
`Liveness probe failed`, it returns the right runbook ranked by match
specificity — instead of the model guessing from a list of filenames.

---

## Requirements

Python 3.9+. **No third-party packages** — the server speaks JSON-RPC 2.0 over
stdio using only the standard library, in keeping with this project's $0 cost
model. `pyyaml` is needed only for `route_symptom`, and is already required by
the validation suite.

---

## Verify it works before wiring it up

```bash
python3 integrations/mcp/server.py --test
```
```json
{"status": "ok", "runbooks_count": 21, "tools": ["list_runbooks", "get_runbook", "get_decision_tree", "query_command_safety", "route_symptom"]}
```

Exercise a tool directly:

```bash
python3 integrations/mcp/server.py --classify "kubectl delete ns prod"
python3 integrations/mcp/server.py --route "137"
```

Or drive the protocol by hand:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python3 integrations/mcp/server.py
```

---

## Client configuration

### Claude Code

```bash
claude mcp add k8s-troubleshooter -- python3 /absolute/path/to/k8s-ai-troubleshooter/integrations/mcp/server.py
```

Then confirm with `/mcp` inside Claude Code.

### Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart the app afterwards. **Paths must be absolute** — the server is launched
without a shell, so `~` and relative paths will not resolve.

### Cursor

`.cursor/mcp.json` in your project, or the global equivalent:

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

### Any other MCP client

Launch `python3 <repo>/integrations/mcp/server.py` as a **stdio** server. It
implements `initialize`, `tools/list`, `tools/call` and `ping`, and echoes back
whichever `protocolVersion` the client requests.

---

## What this does and does not give you

**It does not execute kubectl.** The server serves knowledge — runbooks, trees,
routing, classification. Running commands remains the client's job, under the
client's own permission model.

That separation is deliberate. It means the MCP server has no cluster access, no
credentials, and no ability to change anything. It reads files in this
repository. The blast radius of the server itself is zero.

So a complete setup is usually **both**: this MCP server for the knowledge, and
the platform's own shell tool for execution, gated by that platform's
permissions.

---

## Worked exchange

```text
You:  A pod is showing exit code 137. What now?

Model: [calls route_symptom("137")]
       → runbooks/pods/oomkilled.md, tree decision-trees/pod-failure.yaml,
         first_command: kubectl describe pod <pod> -n <namespace>

       [calls get_runbook("oomkilled")]

       137 is SIGKILL, which in practice means the OOM killer. Following
       oomkilled.md, I need the memory limit versus actual usage.

       [calls query_command_safety("kubectl describe pod api-1 -n prod")]
       → SAFE_READ, automatic_execution_allowed: true

       [runs it via the shell tool]
```

Note the model checked the tier **before** running the command, and used routing
rather than guessing the runbook.

---

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Server not listed in client | Config not reloaded | Fully restart the client; `/mcp` in Claude Code |
| "spawn python3 ENOENT" | `python3` not on the launcher's PATH | Use an absolute interpreter path, e.g. `/usr/bin/python3` |
| Tools appear, calls fail | Relative path in config | Use an absolute path to `server.py` |
| `route_symptom` errors | `pyyaml` missing | `pip install pyyaml` |
| `get_runbook` returns isError | Wrong id | Ids are filenames without `.md`; call `list_runbooks` |
| Server exits immediately | It reads stdin until EOF | Expected when run without a client attached |

---

## Related

- [README.md](README.md) — other platforms
- [../safety-model.md](../safety-model.md)
- [../../integrations/mcp/README.md](../../integrations/mcp/README.md)
