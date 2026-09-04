# ADR-0003: Deterministic Rule Engine Boundary

- Status: Accepted
- Date: 2026-09-04

## Decision

Language and vision models may create candidate clauses, facts, and rule structures. Published compliance outcomes are produced by a deterministic rule engine operating on versioned rules and a frozen project fact snapshot.

## Rationale

Free-form model responses are not reproducible enough for safety-related decisions. A strict boundary allows AI to reduce manual extraction effort without becoming an untraceable source of final compliance status.

## Consequences

- Model output must pass typed schema validation.
- Published rule packages are immutable.
- Missing inputs produce an explicit insufficient-information result.
- Every check stores its inputs, rule version, execution trace, and evidence references.
