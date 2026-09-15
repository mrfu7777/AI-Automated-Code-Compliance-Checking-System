#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: scripts/backup.sh BACKUP_DIRECTORY" >&2
  exit 2
fi

backup_directory=$1
case "$backup_directory" in
  ""|/|.|..)
    echo "Choose a dedicated backup directory." >&2
    exit 2
    ;;
esac

mkdir -p "$backup_directory"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
database_archive="$backup_directory/postgres-$timestamp.dump"

docker compose -f infra/docker-compose.yml exec --no-TTY postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$database_archive"

archive_name=$(basename "$database_archive")
(cd "$backup_directory" && sha256sum "$archive_name" > "$archive_name.sha256")
echo "Database backup created: $database_archive"
echo "Back up the MinIO volume separately before changing or deleting uploaded evidence."
