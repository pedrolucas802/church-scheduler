#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${1:-church_db}"

echo "Reading POSTGRES_* env from container: $CONTAINER"
PGUSER="$(docker exec "$CONTAINER" printenv POSTGRES_USER 2>/dev/null || echo postgres)"
PGPASS="$(docker exec "$CONTAINER" printenv POSTGRES_PASSWORD 2>/dev/null || true)"

if [[ -z "${PGPASS}" ]]; then
  echo "ERROR: POSTGRES_PASSWORD not found in container env."
  echo "Fix: set it in docker-compose for the postgres service."
  exit 1
fi

docker exec -i "$CONTAINER" bash -lc "PGPASSWORD='${PGPASS}' psql -U '${PGUSER}' -d postgres" <<'SQL'
DO $$
BEGIN
  PERFORM pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'church_scheduler' AND pid <> pg_backend_pid();
END $$;

DROP DATABASE IF EXISTS church_scheduler;
DROP ROLE IF EXISTS church_admin;

CREATE ROLE church_admin WITH LOGIN PASSWORD 'church_password';
CREATE DATABASE church_scheduler OWNER church_admin ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE church_scheduler TO church_admin;

\connect church_scheduler
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL

echo "✅ Reset done."

#Run:
# chmod +x scripts/reset_db.sh
# ./scripts/reset_db.sh