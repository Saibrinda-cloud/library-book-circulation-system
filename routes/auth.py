"""Module 1: login, logout and role-based landing."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from db import get_db
from security import DUMMY_HASH, verify_password

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    return redirect(url_for("dashboard.home" if g.user else "auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard.home"))
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        row = get_db().execute(
            "SELECT m.member_id, m.password_hash FROM MEMBERS m WHERE m.email = %s",
            (email,),
        ).fetchone()
        # Always verify a hash (a dummy one if the e-mail is unknown) so timing is similar.
        valid = verify_password(row["password_hash"] if row else DUMMY_HASH, password)
        if row and valid:
            session.clear()                      # new session on login (prevents fixation)
            session["member_id"] = row["member_id"]
            session.permanent = True
            return redirect(url_for("dashboard.home"))
        flash("Incorrect e-mail or password.", "error")
    return render_template("login.html", email=email)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
