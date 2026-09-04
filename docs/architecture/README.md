# Architecture Baseline

## Context

The platform ingests regulations and project files, extracts traceable facts, and executes reviewed compliance rules. Safety-related conclusions must remain deterministic, reproducible, and linked to source evidence.

## M0 decisions

The initial system is a modular monolith with asynchronous workers:

- React and TypeScript provide the browser application.
- FastAPI provides the versioned HTTP API.
- PostgreSQL stores business state and immutable review snapshots.
- Redis carries Celery jobs and short-lived coordination state.
- MinIO stores original files and generated artifacts.
- Celery workers host long-running document, drawing, review, and report pipelines.
- Alembic is the only supported database schema migration mechanism.

The architecture intentionally separates model-assisted extraction from deterministic compliance evaluation. Model outputs enter the domain as candidates and require schema validation and, where required, human verification.

## Stable contracts

The following contracts are established in M0 and extended compatibly in later milestones:

- versioned API prefix;
- structured error envelope;
- core entity identifiers;
- evidence references;
- project facts;
- rules and rule packages;
- check runs and results;
- asynchronous job states;
- immutable source and result versions.

## Architecture decision records

- [ADR-0001: Modular monolith with asynchronous workers](adr/0001-modular-monolith.md)
- [ADR-0002: Evidence-first domain model](adr/0002-evidence-first-domain.md)
- [ADR-0003: Deterministic rule engine boundary](adr/0003-deterministic-rule-engine.md)

## Domain model

See [domain-model.md](domain-model.md) for the initial entity relationship diagram.
