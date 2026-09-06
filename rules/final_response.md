# Final Response Protocol

Every task must finish in a state ready for human review. Tailor your final response based on the task type:

## For Read-Only / Investigation Tasks
Provide a concise summary (2-3 sentences) of your findings, relevant evidence, and recommended next steps.

## For Mutating Tasks
Provide a structured summary using these headers:
* **Changes:** What changed and files affected.
* **Why:** Rationale and alternatives discarded.
* **Validation:** Exact checks run to prove correctness.
* **Risks & Assumptions:** Known risks and assumed variables.
* **Mutation Status:** Explicitly state if commits, pushes, or deployments were performed or if they are pending human review.
