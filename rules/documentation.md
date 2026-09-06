# Living Documentation & Token Efficiency

Project documentation must be treated as "moving documentation" (living docs) that evolves alongside the codebase. It must be designed for extreme token efficiency to prevent AI context window bloat.

## 1. Low-Token Format Rules
* **Conciseness:** Write in short, declarative sentences. Avoid unnecessary filler words or long prose.
* **Formatting:** Use bullet points, tables, and short checklists. They are highly token-efficient and easy for both humans and AI to parse.
* **No Code Duplication:** NEVER copy-paste large blocks of code into documentation. Instead, reference the file path and line numbers (e.g., `See src/auth/login.ts`).
* **Logs & Errors:** Do not store massive stack traces in documentation. Store the specific error message, the root cause, and the fix.

## 2. The "Moving Documentation" Lifecycle
* **Update as you go:** Whenever you make an architectural change, deploy a new service, or solve a complex bug, immediately update the relevant project `README.md` or `docs/` file.
* **Decisions over History:** Store *why* a decision was made in the relevant architecture or design document. Do not document the *history* of the conversation.
* **Pruning:** When updating documentation, actively delete stale, outdated, or duplicate information. The documentation must stay lean.

## 3. Separation of Concerns
* **Project documentation:** Keep repository guidance short and factual; use `README.md` for entry points and focused files under `docs/` for details.
* **`docs/` or `README.md`:** Human-facing documentation. Even here, keep it modular. Use an index (`README.md`) that links to smaller, specific markdown files rather than one giant monolithic document.
