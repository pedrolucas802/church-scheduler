-- Run as a superuser (postgres) in psql
-- This will DROP and recreate the database + user.
-- psql -U postgres -h localhost -f scripts/reset_db.sql

DO $$
BEGIN
  -- drop connections
  PERFORM pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'church_scheduler' AND pid <> pg_backend_pid();
END $$;

DROP DATABASE IF EXISTS church_scheduler;
DROP ROLE IF EXISTS church_admin;

CREATE ROLE church_admin WITH
  LOGIN
  PASSWORD 'church_password'
  CREATEDB;

CREATE DATABASE church_scheduler
  OWNER church_admin
  ENCODING 'UTF8';

GRANT ALL PRIVILEGES ON DATABASE church_scheduler TO church_admin;