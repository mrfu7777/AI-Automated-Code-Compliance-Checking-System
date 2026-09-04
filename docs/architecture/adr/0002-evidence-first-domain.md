# ADR-0002: Evidence-First Domain Model

- Status: Accepted
- Date: 2026-09-04

## Decision

Represent every extracted or manually supplied project fact with explicit evidence. Evidence can point to a document page and region, an image region, a spreadsheet range, an IFC object, a manual assertion, or a derived computation.

## Rationale

Compliance conclusions are only useful when a reviewer can inspect their source. A shared evidence contract also prevents separate OCR, BIM, drawing, and manual-input subsystems from creating incompatible fact models.

## Consequences

- Missing or contradictory evidence is represented explicitly.
- Human verification augments rather than overwrites machine output.
- Review results can link to both regulation evidence and project evidence.
- Storage and API schemas carry source versions and location metadata from the start.
