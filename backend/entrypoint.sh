#!/bin/bash
set -e

echo "Waiting for postgres..."
while ! pg_isready -h postgres -U trapper > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready!"

# Only run migrations if RUN_MIGRATIONS is set to true (for backend container only)
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "Skipping migrations (not the migration runner)"
fi

echo "Starting application..."
exec "$@"
