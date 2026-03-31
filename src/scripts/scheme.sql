-- =========================================================
-- Church Scheduler (PostgreSQL) — schema equivalent to your SQLAlchemy models
-- Safe to run multiple times (IF NOT EXISTS everywhere possible)
-- =========================================================

BEGIN;

-- Optional: keep everything under a dedicated schema
-- CREATE SCHEMA IF NOT EXISTS church;
-- SET search_path TO church;

-- -------------------------
-- admin_users
-- -------------------------
CREATE TABLE IF NOT EXISTS admin_users (
  id              BIGSERIAL PRIMARY KEY,
  username        TEXT NOT NULL UNIQUE,
  password_hash   TEXT NOT NULL,
  active          INTEGER NOT NULL DEFAULT 1,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until    TEXT NULL,   -- ISO string for MVP
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

-- -------------------------
-- volunteers
-- -------------------------
CREATE TABLE IF NOT EXISTS volunteers (
  id         BIGSERIAL PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  email      TEXT NULL,
  phone      TEXT NULL,
  active     INTEGER NOT NULL DEFAULT 1,
  thu_ok     INTEGER NOT NULL DEFAULT 1,
  sun_ok     INTEGER NOT NULL DEFAULT 1,
  can_obs    INTEGER NOT NULL DEFAULT 1,
  can_fixed  INTEGER NOT NULL DEFAULT 1,
  can_mobile INTEGER NOT NULL DEFAULT 1
);

-- -------------------------
-- services
-- -------------------------
CREATE TABLE IF NOT EXISTS services (
  id     BIGSERIAL PRIMARY KEY,
  dt_iso TEXT NOT NULL UNIQUE
);

-- -------------------------
-- assignments
-- -------------------------
CREATE TABLE IF NOT EXISTS assignments (
  id           BIGSERIAL PRIMARY KEY,
  service_id   BIGINT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
  role         TEXT NOT NULL,
  volunteer_id BIGINT NULL REFERENCES volunteers(id) ON DELETE SET NULL,
  CONSTRAINT uq_assignments_service_role UNIQUE (service_id, role)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_assignments_service_id ON assignments(service_id);
CREATE INDEX IF NOT EXISTS idx_assignments_volunteer_id ON assignments(volunteer_id);

-- -------------------------
-- swap_requests
-- -------------------------
CREATE TABLE IF NOT EXISTS swap_requests (
  id                        BIGSERIAL PRIMARY KEY,
  assignment_id             BIGINT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
  requested_by_volunteer_id BIGINT NULL REFERENCES volunteers(id) ON DELETE SET NULL,
  replacement_volunteer_id  BIGINT NULL REFERENCES volunteers(id) ON DELETE SET NULL,
  reason                    TEXT NULL,
  status                    TEXT NOT NULL DEFAULT 'PENDING',
  created_at                TEXT NOT NULL,
  resolved_at               TEXT NULL,
  resolved_by_admin         TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_swap_requests_status ON swap_requests(status);
CREATE INDEX IF NOT EXISTS idx_swap_requests_assignment_id ON swap_requests(assignment_id);

-- -------------------------
-- reminder_jobs
-- -------------------------
CREATE TABLE IF NOT EXISTS reminder_jobs (
  id            BIGSERIAL PRIMARY KEY,
  assignment_id BIGINT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
  send_at_iso   TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'PENDING',
  attempts      INTEGER NOT NULL DEFAULT 0,
  last_error    TEXT NULL,
  created_at    TEXT NOT NULL,
  sent_at       TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_reminder_jobs_status_send_at ON reminder_jobs(status, send_at_iso);
CREATE INDEX IF NOT EXISTS idx_reminder_jobs_assignment_id ON reminder_jobs(assignment_id);

-- -------------------------
-- app_settings
-- -------------------------
CREATE TABLE IF NOT EXISTS app_settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NULL,
  updated_at TEXT NOT NULL
);

COMMIT;

-- =========================================================
-- If you already have an existing DB and just need to ensure
-- the "email" column exists on volunteers, run:
-- =========================================================
-- ALTER TABLE volunteers ADD COLUMN IF NOT EXISTS email TEXT;
