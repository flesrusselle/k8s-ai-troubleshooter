# RTK (Rust Token Killer) Optimization

To preserve context window and reduce token usage, always prefer using `rtk` when running shell commands.

## RTK Usage
When available, prefix noisy commands with `rtk`:
* **Files:** `rtk ls`, `rtk read <file>`, `rtk grep <pattern>`
* **Git:** `rtk git status`, `rtk git diff`, `rtk git log`
* **Testing:** `rtk pytest`, `rtk cargo test`, `rtk jest`
* **Containers & K8s:** `rtk docker ps`, `rtk kubectl pods`, `rtk kubectl logs <pod>`

## Auto-Rewrite
For supported agents (like Antigravity), RTK might automatically rewrite bash commands if initialized via `rtk init --agent antigravity`. However, if you notice output is too verbose, explicitly use the `rtk` prefix.
