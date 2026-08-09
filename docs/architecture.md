# Architecture of `k8s-ai-troubleshooter`

`k8s-ai-troubleshooter` is built as a modular, open, local-first knowledge base layer.

```text
┌─────────────────────────────────────────────────────────────┐
│                    AI Assistant / Client                    │
│   (Antigravity, Claude Code, Cursor, ChatGPT, Copilot, MCP) │
└──────────────────────────────┬──────────────────────────────┘
                               │ Reads Runbooks & Decision Trees
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    k8s-ai-troubleshooter                    │
│  ├── Schemas (JSON Schema validation)                       │
│  ├── Runbooks (Markdown diagnostic guides)                 │
│  ├── Decision Trees (Machine-readable YAML logic)          │
│  ├── Command Catalog (Classified safety metadata)           │
│  └── Integrations & MCP Adapter                             │
└──────────────────────────────┬──────────────────────────────┘
                               │ Safe Diagnostic Queries (SAFE_READ)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                      │
│             (API Server, Workloads, Helm, Nodes)            │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

1. **Schemas Layer (`schemas/`)**: Strict JSON Schemas ensuring runbooks, decision trees, and command catalogs remain valid.
2. **Command Safety Catalog (`commands/`)**: Defines commands, output formats, failure modes, and safety classifications.
3. **Decision Trees (`decision-trees/`)**: Declarative YAML workflows guiding diagnostic traversal.
4. **Runbooks (`runbooks/`)**: Detailed Markdown documentation explaining symptoms, diagnosis, evidence collection, and remediation.
5. **Integrations (`integrations/`)**: Platform-specific adapters and prompts enabling AI assistants to load the engine natively.
