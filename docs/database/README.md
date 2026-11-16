# Basera database (PostgreSQL)

| File | What it is |
|---|---|
| `erd_transcription.md` | The ERD from the Sprint 0 technical proposal, written out entity by entity, with every decision made while implementing it. |
| `schema.sql` | **Generated**, read-only PostgreSQL DDL for the project's tables (what `migrate` will create). Do not run it by hand. |
| `setup_postgres.sql` | One-time script that creates the `basera_app` role and the `basera` database. |

The models live in `accounts/models.py` (User), `catalog/models.py` (Region,
PlantSpecies, SpeciesRegion), `growprofiles/models.py` (GrowProfile) and
`orders/models.py` (CartItem, Order, OrderItem).

## One-time setup on Windows (PostgreSQL 18)

Commands are for **PowerShell**, run from the project folder
(`C:\Users\Wajiz.pk\Desktop\Basera`). `psql` is not on PATH, so the full path is used.

### 1. Create the role and database

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -f docs\database\setup_postgres.sql
```

It first asks for the **postgres** superuser password (the one chosen when
PostgreSQL was installed). Then the script will ask you to choose the
`basera_app` password (`Enter new password for user "basera_app":`, twice).
Remember it for the next step. Expected output ends with
`You are now connected to database "basera"`, `ALTER SCHEMA` and `GRANT`.

If the two `basera_app` passwords you type **don't match**, psql prints
`Passwords didn't match.` and the script stops before creating the database.
Start over as described below.

The script is **not re-runnable**: a second run stops at `CREATE ROLE` because
the role already exists. To start over, open psql as postgres:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost
```

then run `DROP DATABASE IF EXISTS basera;` and `DROP ROLE IF EXISTS basera_app;`, quit with `\q`,
and run step 1 again.

### 2. Put the password in `.env`

Open `.env` in the project root and fill in the line `DB_PASSWORD=` with the
password you chose in step 1 (no quotes, no spaces). `.env` is git-ignored; never
commit it. `.env.example` is the committed template.

Check the connection:

```powershell
.venv\Scripts\python manage.py showmigrations
```

It should list the apps with `[ ]` next to each migration and no connection error.

### 3. Create the tables

```powershell
.venv\Scripts\python manage.py migrate
```

### 4. Create an admin account

```powershell
.venv\Scripts\python manage.py createsuperuser
```

It asks for **Email address**, **Full name** and a password (at least 8
characters). The account gets role `ADMIN` and `is_superuser`, and can sign in
at http://127.0.0.1:8000/admin/.

About admin access (`is_staff`): the user table has no `is_staff` column. It is a
read-only property that is true for active users with role `ADMIN` (or
superusers). So you cannot pass `is_staff=...` to `create_user()` or `User(...)`,
and you cannot filter querysets on `is_staff`; use `role="ADMIN"` instead. Role
ADMIN only lets a user log into the admin site: unless they are a superuser they
still need model permissions (through groups or user permissions) to see or
change anything there. The database also enforces that every superuser has role
ADMIN.

### 5. Restart the dev server

```powershell
.venv\Scripts\python manage.py runserver
```

`runserver` checks the database at startup, so it does not serve pages while
the database is unreachable (for example while `DB_PASSWORD` is still empty).
A server that was already running does not notice edits to `.env`; stop it
(Ctrl+C) and start it again.

## Running the tests

```powershell
.venv\Scripts\python manage.py test
```

Django creates and drops a temporary `test_basera` database (this is why the
setup script gives `basera_app` the CREATEDB right).

## Old SQLite file

`db.sqlite3` in the project root is the obsolete pre-PostgreSQL development
database. Nothing uses it any more and it can be deleted.

## Changing the schema later

1. Edit the models.
2. `.venv\Scripts\python manage.py makemigrations`
3. `.venv\Scripts\python manage.py migrate`
4. Regenerate `schema.sql` (for example with `sqlmigrate <app> <migration>` once
   the database is reachable) and update `erd_transcription.md` if the ERD changed.

Use the Django ORM only (no raw SQL), so the code keeps working on any database.
