#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: CONFIRM_RESTORE=code-compliance scripts/restore.sh DATABASE_ARCHIVE" >&2
  exit 2
fi

if [ "${CONFIRM_RESTORE:-}" != "code-compliance" ]; then
  echo "Restore replaces the application database." >&2
  echo "Set CONFIRM_RESTORE=code-compliance after verifying the target stack." >&2
  exit 2
fi

database_archive=$1
if [ ! -f "$database_archive" ]; then
  echo "Backup archive not found: $database_archive" >&2
  exit 2
fi

archive_directory=$(dirname "$database_archive")
archive_name=$(basename "$database_archive")
(cd "$archive_directory" && sha256sum -c "$archive_name.sha256")
container_archive=/tmp/code-compliance-restore.dump
docker compose -f infra/docker-compose.yml cp "$database_archive" "postgres:$container_archive"
docker compose -f infra/docker-compose.yml exec --no-TTY postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/code-compliance-restore.dump'
docker compose -f infra/docker-compose.yml exec --no-TTY postgres rm -f "$container_archive"
echo "Database restore completed. Run the readiness and pilot smoke checks next."
