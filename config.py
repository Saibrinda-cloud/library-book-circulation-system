"""Application settings, read from environment variables (and the .env file)."""
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

# Load ".env" from the project folder. Variables already set in the environment win.
load_dotenv(Path(__file__).with_name(".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "5432"))
    DB_NAME = os.environ.get("DB_NAME", "library_db")
    DB_USER = os.environ.get("DB_USER", "lms_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

    # Library policy (project rules: 14-day loan, Rs. 2 per overdue day).
    LOAN_PERIOD_DAYS = int(os.environ.get("LOAN_PERIOD_DAYS", "14"))
    FINE_PER_DAY = Decimal(os.environ.get("FINE_PER_DAY", "2.00"))

    PER_PAGE = 12

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # set True when the site is served over HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
