-- create_database.sql
-- Run ONCE as the PostgreSQL superuser (for example: psql -U postgres -f sql/create_database.sql).
-- The user name, password and database name must match your .env file.

CREATE USER lms_user WITH PASSWORD 'lms_password_change_me';
CREATE DATABASE library_db OWNER lms_user;

-- Optional: a second, empty database used only by smoke_test.py (it is wiped on every run).
CREATE DATABASE library_test OWNER lms_user;
