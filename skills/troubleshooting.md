# Troubleshooting & Diagnostics

## Dead Ends & Boundaries
* **Bounded Investigation:** Make a maximum of 3 meaningful attempts to fix a failure. Every attempt must add new information.
* **Boundary Detection:** Stop investigation at the earliest layer that explains the failure (e.g., if Maven fails, do not investigate the Dockerfile).

## The Identical Error Rule
If a change was intended to fix an error and the exact same error remains, DO NOT repeat the same fix. Revert the ineffective change and verify effective configuration.

## Diagnostic Pivot
If you hit a stop condition, 3 failed attempts, or the Identical Error limit, you MUST explicitly output `[DIAGNOSTIC PIVOT]`, state why the current hypothesis failed, and ask the user for fresh context or suggest checking a completely different architectural layer.

## Diff-First Investigation
When debugging regressions, inspect the smallest relevant diff first (`git diff`, `helm diff`, `terraform plan`) and compare against the last known-good state.
