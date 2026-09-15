# M7 Pilot Acceptance Plan and Record

Status: **RC readiness implemented; real architect acceptance pending.** No customer drawing or
architect observation was available during development, so this document must not be marked passed
from synthetic data alone.

## Pilot sample

- One authorized existing-building renovation project; optionally one control project.
- One national published rule pack with 20–30 architect-reviewed rules; optional supplementary pack.
- One or two architects who were not guided through every screen by the developer.
- A manually reviewed expected-result sheet covering serious non-compliance, compliance boundaries,
  missing inputs, exceptions, conflicts, revisions, and evidence links.

## Acceptance record

| Criterion | Required evidence | Status |
| --- | --- | --- |
| No known serious issue is reported compliant | Golden Set and architect discrepancy review | Pending pilot |
| Every definite conclusion has project and regulation evidence | Workbench/report sample audit | Automated contract covered; pilot pending |
| Missing data produces actionable requests | Missing-information endpoint and architect review | Implemented; pilot pending |
| Architect independently completes the flow | Observed session and feedback record | Pending pilot |
| Database and evidence backups restore | Isolated restore drill record | PostgreSQL CI covered; full drill pending |
| Worker retry creates no duplicate result | Automated idempotency regression | Passed locally |
| Model outage preserves deterministic review | Degradation regression and operator observation | Passed locally; pilot pending |
| Pilot user recognizes useful value | Recorded feedback and time/quality comparison | Pending pilot |
| M1–M6 behavior remains intact | Full automated regression | Pending M7 CI |

## Release decision

V1.0 may proceed only when all critical/high discrepancies are resolved or explicitly rejected by a
qualified owner, the full backup/evidence restore passes, and the architect confirms useful value.
After M7, V1.0 is a hardening release: blocker fixes and validated rule/data expansion only, with no
parallel rewrite of the M1–M7 project, evidence, rules, snapshots, jobs, or review workflow.
