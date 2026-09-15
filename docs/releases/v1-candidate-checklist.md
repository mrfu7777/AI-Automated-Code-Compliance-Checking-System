# V1.0 Candidate Checklist

- [ ] M7 pilot acceptance record is complete and signed by the architect and release owner.
- [ ] Zero unresolved critical/high false-compliant or evidence-integrity defects.
- [ ] Pilot rule pack contains 20–30 reviewed rules with positive, negative, boundary, missing-data,
      exception, unit-conversion, conflict, and revision regression cases.
- [ ] Full PostgreSQL and MinIO restore drill passed in an isolated environment.
- [ ] Security checklist passed; production secrets rotated after the pilot.
- [ ] M1–M7 regression, migration, frontend, Compose, and backup/restore CI are green.
- [ ] Deployment tag, rollback point, retention policy, support owner, and incident procedure recorded.
- [ ] Known limitations and preliminary-review disclaimer accepted by every pilot user.
- [ ] V1.0 scope contains hardening and blocker fixes only; no workflow or data-model rewrite.
