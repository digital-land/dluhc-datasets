#!/bin/sh
set -eu

dump_path=/code/data/latest_backup.dump

if [ ! -f "$dump_path" ]; then
    echo "Database backup not found at $dump_path" >&2
    exit 1
fi

has_data="$(
    psql "$DATABASE_URL" --tuples-only --no-align --command \
        "SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'dataset'
        ) AND EXISTS (SELECT 1 FROM dataset LIMIT 1);" 2>/dev/null || true
)"

if [ "$has_data" = "t" ]; then
    echo "Database already contains dataset data; skipping backup restore."
    exit 0
fi

echo "Loading local database backup from $dump_path"
pg_restore \
    --clean \
    --if-exists \
    --no-acl \
    --no-owner \
    --dbname "$DATABASE_URL" \
    "$dump_path"
echo "Database backup loaded."
