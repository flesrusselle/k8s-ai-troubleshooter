# AI Assistant Integration Guide

`k8s-ai-troubleshooter` supports seamless integration across multiple AI platforms:

---

## 🤖 Supported Integration Targets

| AI Platform | Preset File Location | Integration Method |
| :--- | :--- | :--- |
| **Antigravity AI** | `integrations/antigravity/SKILL.md` | Skill folder loading |
| **Claude Code** | `integrations/claude/CLAUDE.md` | Repository instructions |
| **Cursor** | `integrations/cursor/.cursorrules` | Project rules file |
| **ChatGPT** | `integrations/chatgpt/instructions.md` | Custom GPT / Project Instructions |
| **GitHub Copilot** | `integrations/copilot/instructions.md` | Copilot Workspace instructions |
| **Generic AI** | `integrations/generic/system-prompt.md` | Portable System Prompt |
| **MCP Clients** | `integrations/mcp/server.py` | Model Context Protocol Server |

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
