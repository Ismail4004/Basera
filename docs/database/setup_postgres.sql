-- =============================================================================
-- Basera: one-time PostgreSQL setup (run as the "postgres" superuser)
-- =============================================================================
-- Creates the application role and database that Django connects to.
-- Step-by-step instructions: docs/database/README.md
--
-- No password is stored in this file: the \password line below makes psql ask
-- you to choose the basera_app password while the script runs. Put that same
-- password in DB_PASSWORD in the project's .env file.
--
-- Not re-runnable: a second run stops at CREATE ROLE (role already exists).
-- It also stops if the two basera_app passwords you type don't match.
-- To start over, as postgres:  DROP DATABASE IF EXISTS basera;  DROP ROLE IF EXISTS basera_app;
--
-- Tables are NOT created here: `manage.py migrate` creates them.
-- =============================================================================

\set ON_ERROR_STOP on

-- 1. Application login role (not a superuser), created without a password.
--    CREATEDB lets `manage.py test` create and drop its throwaway test_basera
--    database; remove it with  ALTER ROLE basera_app NOCREATEDB;  if unwanted.
CREATE ROLE basera_app WITH LOGIN NOSUPERUSER NOCREATEROLE CREATEDB;

-- psql prompts for the new password twice (it is sent hashed, not logged).
\password basera_app

-- Settings Django recommends for its connection role
-- (https://docs.djangoproject.com/en/6.1/ref/databases/#optimizing-postgresql-s-configuration).
ALTER ROLE basera_app SET client_encoding TO 'UTF8';
ALTER ROLE basera_app SET default_transaction_isolation TO 'read committed';
ALTER ROLE basera_app SET timezone TO 'UTC';

-- 2. Database owned by the application role, UTF8 encoded.
--    template0 is required when choosing an encoding explicitly.
CREATE DATABASE basera
    WITH OWNER = basera_app
         ENCODING = 'UTF8'
         TEMPLATE = template0;

-- 3. Schema privileges on "public" in the new database, stated explicitly so
--    migrations can create tables there.
\connect basera
ALTER SCHEMA public OWNER TO basera_app;
GRANT USAGE, CREATE ON SCHEMA public TO basera_app;
