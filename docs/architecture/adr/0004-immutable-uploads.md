# ADR-0004: Immutable uploads and persistent asynchronous jobs

- Status: Accepted
- Date: 2026-09-09

## Context

Regulations and project drawings change over time. A compliance result must continue to identify
the exact bytes that were reviewed, and processing must survive API or worker restarts. Passing
large files through Redis or storing progress only in process memory would make that impossible.

## Decision

- Each logical ProjectFile has append-only FileVersion records.
- Original bytes are stored under unique MinIO object keys and are never overwritten.
- PostgreSQL stores size, media type, SHA-256, version number, ownership, and object location.
- Uploads are streamed through a bounded spool and rejected above the configured limit.
- The API commits a persistent Job before publishing its UUID to Celery.
- Workers receive stable identifiers, reload state, and persist progress, output, and failures.
- Failed jobs may be manually retried up to their stored maximum attempt count.
- File and job queries are scoped to the current actor's organization.
- Downloads use short-lived presigned URLs generated for a browser-accessible MinIO endpoint.

## Consequences

Historical bytes and processing state remain reproducible after revisions and service restarts.
M2 can attach regulation parsing to the same FileVersion and Job contracts. Storage cleanup and
orphan reconciliation must be added before production use because object storage and PostgreSQL
cannot share one atomic transaction.
