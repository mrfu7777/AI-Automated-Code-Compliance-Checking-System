# M7 Known Limitations and Defect Policy

## Known limitations

- Rule coverage is intentionally limited to architect-reviewed pilot rules; unencoded clauses remain
  manual review responsibilities.
- Drawing understanding is candidate generation plus calibrated human annotation, not general CAD
  reasoning or automatic proof of geometry.
- Only PDF, DOCX, XLSX, and IFC uploads are supported. Native DWG is outside M7.
- Regulation OCR and segmentation require page-by-page human verification before publication.
- Project facts require human verification and may not capture exceptions hidden in unprocessed files.
- API-key authentication is appropriate for a controlled pilot, not enterprise SSO/MFA provisioning.
- The bootstrap key is the pilot administrator; M7 has no user-provisioning interface or delegated
  per-user admin-key issuance. Named architect keys created by the default pilot account share that
  account's audit identity.
- The optional external-model guard exists, but no external model adapter is enabled in M7. Reported
  model calls and cost therefore remain zero.
- Metrics are organization-level operational counters, not a full Prometheus/tracing dashboard.
- The included backup script covers PostgreSQL; MinIO evidence requires a deployment-specific volume
  snapshot or object mirror and a joint restore drill.
- Real-world fire-code accuracy and user value are unaccepted until the recorded architect pilot runs.

## Defect policy

A known serious false-compliant result, missing/incorrect evidence for a definite conclusion,
cross-tenant exposure, unrecoverable evidence, or non-idempotent duplicate finding is a release
blocker. False positives, missed extraction candidates, and usability problems are recorded through
pilot feedback, reproduced against immutable inputs, classified by severity, and added to the Golden
Set before a fix is accepted.
