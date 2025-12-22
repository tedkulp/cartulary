#!/bin/bash
set -e

echo "Waiting for postgres..."
while ! pg_isready -h postgres -U trapper > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec "$@"
