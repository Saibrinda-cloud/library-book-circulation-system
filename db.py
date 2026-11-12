"""Database access with Psycopg 3: one connection per request, closed automatically."""
import psycopg
from flask import current_app, g
from psycopg.rows import dict_row


class DatabaseUnavailable(Exception):
    """Raised when the application cannot connect to PostgreSQL."""


def get_db():
    """Return this request's connection (opened on first use).

    The connection is in autocommit mode: a single statement is its own transaction.
    Operations that must succeed or fail together use "with conn.transaction():".
    """
    if "db" not in g:
        cfg = current_app.config
        try:
            g.db = psycopg.connect(
                host=cfg["DB_HOST"],
                port=cfg["DB_PORT"],
                dbname=cfg["DB_NAME"],
                user=cfg["DB_USER"],
                password=cfg["DB_PASSWORD"],
                connect_timeout=5,
                autocommit=True,
                row_factory=dict_row,
            )
        except psycopg.OperationalError as exc:
            current_app.logger.error("Database connection failed: %s", exc)
            raise DatabaseUnavailable() from exc
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
