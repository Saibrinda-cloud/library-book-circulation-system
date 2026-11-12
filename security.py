"""Password hashing, CSRF protection, current-user loading and role checks."""
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db

# Portable, salted PBKDF2 hashes (available in every Python build).
HASH_METHOD = "pbkdf2:sha256"
# Checked when the e-mail is unknown, so both failures take similar time.
DUMMY_HASH = generate_password_hash("not-a-real-password", method=HASH_METHOD)


def hash_password(password):
    return generate_password_hash(password, method=HASH_METHOD)


def verify_password(stored_hash, password):
    return check_password_hash(stored_hash, password)


# ---------------------------------------------------------------- CSRF
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def verify_csrf():
    """Reject any POST request that does not carry this session's CSRF token."""
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400, "The form expired or is invalid. Go back, reload the page and try again.")


# ---------------------------------------------------------------- current user
def load_current_user():
    """Look the logged-in member up in the database on every request.

    The role comes from the database, not from the cookie, so a changed role or a
    removed account takes effect immediately.
    """
    g.user = None
    if request.endpoint in (None, "static"):
        return
    member_id = session.get("member_id")
    if member_id is None:
        return
    row = get_db().execute(
        "SELECT m.member_id, m.full_name, m.email, r.role_name "
        "FROM MEMBERS m INNER JOIN ROLES r ON r.role_id = m.role_id "
        "WHERE m.member_id = %s",
        (member_id,),
    ).fetchone()
    if row is None:
        session.clear()
    else:
        g.user = row


# ---------------------------------------------------------------- decorators
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role_name):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("auth.login"))
            if g.user["role_name"] != role_name:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


librarian_required = role_required("Librarian")
student_required = role_required("Student")
