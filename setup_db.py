"""Build the database: tables, views, demo members and sample data.

    python setup_db.py            create everything (database must be empty)
    python setup_db.py --reset    DROP all project tables and views first, then rebuild
    python setup_db.py --schema-only   tables and views only (no demo data, no accounts)
"""
import argparse
import sys
from pathlib import Path

import psycopg

from config import Config
from seed_users import connect, seed_members

SQL_DIR = Path(__file__).with_name("sql")


def run_script(conn, filename):
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    with conn.transaction():
        conn.execute(sql)  # no parameters, so a multi-statement script is allowed
    print(f"  ran {filename}")


def build(reset=False, schema_only=False):
    with connect() as conn:
        if reset:
            run_script(conn, "reset.sql")
        run_script(conn, "schema.sql")
        run_script(conn, "views.sql")
        if not schema_only:
            seed_members(conn)
            print("  created demo members (seed_users)")
            run_script(conn, "seed.sql")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop existing project tables first")
    parser.add_argument("--schema-only", action="store_true", help="skip demo members and sample data")
    args = parser.parse_args()
    print(f"Setting up database '{Config.DB_NAME}' on {Config.DB_HOST}:{Config.DB_PORT} ...")
    try:
        build(reset=args.reset, schema_only=args.schema_only)
    except psycopg.errors.DuplicateTable:
        sys.exit("Tables already exist. Run again with --reset to drop and rebuild them (this deletes data).")
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to PostgreSQL: {exc}\nCheck the DB_* values in your .env file.")
    print("Done.")


if __name__ == "__main__":
    main()
