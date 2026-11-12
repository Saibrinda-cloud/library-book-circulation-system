"""Flask application factory for the Library Management System.

Run with:  flask --app app run      (or)      python app.py
"""
import os

import psycopg
from flask import Flask, render_template, request, url_for

import db
import security
from config import Config
from db import DatabaseUnavailable


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    key = app.config.get("SECRET_KEY") or ""
    if not key or key.startswith("replace-with"):
        raise RuntimeError(
            "SECRET_KEY is not set. Copy .env.example to .env and set SECRET_KEY to a random value:\n"
            '  python -c "import secrets; print(secrets.token_hex(32))"'
        )

    db.init_app(app)
    app.before_request(security.verify_csrf)
    app.before_request(security.load_current_user)

    # ---- template helpers
    @app.template_filter("money")
    def money(value):
        return "Rs. {:,.2f}".format(value or 0)

    @app.template_filter("fdate")
    def fdate(value):
        return value.strftime("%d %b %Y") if value else "\u2013"

    @app.template_filter("stars")
    def stars(value):
        n = max(0, min(5, int(round(float(value or 0)))))
        return "\u2605" * n + "\u2606" * (5 - n)

    def page_url(n):
        """URL of the current list page with ?page=n, keeping the other filters."""
        args = request.args.to_dict()
        args["page"] = n
        return url_for(request.endpoint, **(request.view_args or {}), **args)

    # Jinja globals are visible inside imported macros (context-processor values are not).
    app.jinja_env.globals["page_url"] = page_url
    app.jinja_env.globals["csrf_token"] = security.csrf_token

    @app.context_processor
    def inject_globals():
        return {
            "fine_per_day": app.config["FINE_PER_DAY"],
            "loan_days": app.config["LOAN_PERIOD_DAYS"],
        }

    # ---- blueprints
    from routes import auth, books, circulation, dashboard, fines, members, reports, reviews
    for module in (auth, dashboard, books, reviews, members, circulation, fines, reports):
        app.register_blueprint(module.bp)

    # ---- error pages
    def show_error(code, title, message):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return show_error(400, "Request not accepted", getattr(e, "description", "Bad request."))

    @app.errorhandler(403)
    def forbidden(e):
        return show_error(403, "Not allowed", "Your account does not have permission to open this page.")

    @app.errorhandler(404)
    def not_found(e):
        return show_error(404, "Page not found", "The page or record you asked for does not exist.")

    @app.errorhandler(DatabaseUnavailable)
    @app.errorhandler(psycopg.OperationalError)
    def database_down(e):
        return show_error(503, "Database unavailable",
                          "The application cannot reach PostgreSQL. Check that the database "
                          "server is running and that the DB_* values in .env are correct.")

    @app.errorhandler(psycopg.Error)
    def database_error(e):
        app.logger.exception("Database error")
        return show_error(500, "Database error", "The database rejected the request. Nothing was saved.")

    @app.errorhandler(500)
    def server_error(e):
        return show_error(500, "Something went wrong", "An unexpected error occurred. Nothing was saved.")

    return app


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1")
