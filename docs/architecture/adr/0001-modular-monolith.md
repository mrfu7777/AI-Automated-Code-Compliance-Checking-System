# ADR-0001: Modular Monolith with Asynchronous Workers

- Status: Accepted
- Date: 2026-09-04

## Decision

Use one FastAPI application for business modules and Celery workers for long-running processing. Keep the frontend in the same repository. Do not split domain modules into networked microservices during the initial product milestones.

## Rationale

The product is developed by a small team and needs transactional consistency across files, standards, facts, rules, and review results. A modular monolith limits operational overhead while explicit module boundaries and worker queues preserve a future scaling path.

## Consequences

- Modules communicate through Python contracts instead of private HTTP APIs.
- CPU-heavy and long-running work executes outside API request processes.
- Workers can later be deployed and scaled by workload type.
- Database and API compatibility remain release-gated concerns.
