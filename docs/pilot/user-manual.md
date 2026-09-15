# Architect Pilot User Manual

## Purpose and boundary

Use this release for preliminary internal fire-code review. It does not issue approval, certify a
design, replace a complete code analysis, or remove the architect's responsibility to confirm the
applicable law, document completeness, geometry, exceptions, and final conclusion.

## One complete pilot flow

1. Enter the API key supplied by the pilot administrator. It remains in the current browser session.
2. Create the project and record jurisdiction, design date, and building type as accurately as the
   current API permits.
3. Upload only authorized PDF, DOCX, XLSX, or IFC material. Keep each logical document name stable;
   replacement uploads become immutable new versions.
4. Upload the regulation as `regulation_source`, parse it, compare extracted clauses with the source
   pages, correct errors, review every active clause, and publish the exact edition.
5. Bind reviewed rule templates to the correct clauses. Validate scope, threshold, units, exceptions,
   dependencies, and boundary tests before reviewing and publishing the pack.
6. Extract project documents/drawings. Verify or reject every candidate; unresolved conflicts never
   become active facts. Add manual facts only with an evidence-based justification.
7. Select the exact published rule pack or packs. Resolve any cross-code conflict explicitly and run
   the immutable check.
8. Review each finding in three columns: conclusion, project evidence, and regulation basis. A
   compliant result without both evidence types is a defect, not an acceptance.
9. Complete every missing-information action or mark the issue for manual review. Never interpret
   missing data as compliance.
10. Export the preliminary report, upload revisions, run an incremental recheck, and compare it with
    the immutable baseline.
11. Record false positives, false negatives, evidence problems, usability problems, and observed
    time saved in Pilot Acceptance. Critical or safety-related feedback stops acceptance.

## If something fails

Do not repeatedly upload the same file. Check the persisted job status and error; retry a failed job
once after correcting its cause. If the model path is unavailable, continue with verified facts and
deterministic checks. Give the administrator the request ID, job ID, project ID, and UTC time—never
send an API key in an issue or screenshot.
