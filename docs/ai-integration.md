# AI Assistant Integration Guide

`k8s-ai-troubleshooter` supports seamless integration across multiple AI platforms:

---

## 🤖 Supported Integration Targets

| AI Platform | Preset File Location | Detailed Guide |
| :--- | :--- | :--- |
| **Antigravity AI** | `integrations/antigravity/SKILL.md` | [usage/antigravity.md](usage/antigravity.md) |
| **Claude Code** | `integrations/claude/CLAUDE.md` | [usage/claude-code.md](usage/claude-code.md) |
| **Cursor** | `integrations/cursor/.cursorrules` | [usage/cursor.md](usage/cursor.md) |
| **ChatGPT** | `integrations/chatgpt/instructions.md` | [usage/chatgpt.md](usage/chatgpt.md) |
| **GitHub Copilot** | `integrations/copilot/instructions.md` | [usage/copilot.md](usage/copilot.md) |
| **Generic AI** | `integrations/generic/system-prompt.md` | [usage/generic-llm.md](usage/generic-llm.md) |
| **MCP Clients** | `integrations/mcp/server.py` | [usage/mcp.md](usage/mcp.md) |

Start at the [usage index](usage/README.md) if you are not sure which mode fits.

---

## 🔒 Mandatory AI Response Schema

All AI assistants using `k8s-ai-troubleshooter` must structure responses cleanly:

```markdown
## Situation
[Brief overview of reported issue]

## What I Checked
[List of SAFE_READ commands executed]

## Evidence
[Key logs, exit codes, container states, events]

## Findings & Hypothesis
[Detailed analysis]

## Likely Root Cause
[Evidence-backed root cause]

## Confidence Level
[High / Medium / Low]

## Recommended Remediation
[Exact remediation command and expected impact]

## Human Approval Required
[Explicit request for human approval before execution]
```
