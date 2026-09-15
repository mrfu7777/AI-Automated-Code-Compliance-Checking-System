# Backup and Restore Drill Record

## Automated proof

The Compose CI job creates a PostgreSQL custom-format archive, restores it into an isolated scratch
database, and removes the scratch database. This proves archive readability and schema restoration
on every main-branch build; it does not prove restoration of customer evidence objects.

## Operator drill

1. Record the Git tag, migration head, database name, MinIO bucket, UTC start time, and operator.
2. Run `scripts/backup.sh backups/<date>` from the repository root.
3. Back up the complete MinIO bucket/volume using the deployment provider's snapshot or `mc mirror`.
4. Verify database SHA-256 and object counts; store both backups under the same drill identifier.
5. Start an isolated recovery stack with different volumes and credentials.
6. Run `CONFIRM_RESTORE=code-compliance scripts/restore.sh <archive>` against that isolated stack.
7. Restore MinIO, start API/worker/web, and verify `/ready`.
8. Open one regulation clause, project evidence item, completed check, and report. Compare stored file
   hashes and review input hashes with the source system.
9. Record UTC recovery time, row/object counts, discrepancies, and corrective actions.
10. Destroy only the isolated recovery environment after review.

## M7 record

| Field | Result |
| --- | --- |
| Automated PostgreSQL archive/restore | Implemented in CI |
| Local automated test date | Pending first M7 CI run |
| MinIO evidence restore | Pending deployment-specific operator drill |
| Target RPO/RTO | Must be agreed with the pilot owner |
| Pilot sign-off | Pending |

A real pilot cannot pass backup acceptance until the database and matching evidence objects have
been restored in an isolated environment and opened successfully.
