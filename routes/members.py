"""Module 1 (member management by the librarian) plus a librarian view of a member's history."""
import psycopg
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from security import hash_password, librarian_required
from utils import Pagination, get_page, like_pattern
from validation import validate_member

bp = Blueprint("members", __name__, url_prefix="/members")


def _roles(conn):
    return conn.execute("SELECT role_id, role_name FROM ROLES ORDER BY role_name").fetchall()


@bp.route("/")
@librarian_required
def list_members():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    conditions, params = [], []
    if q:
        conditions.append("(m.full_name ILIKE %s OR m.email ILIKE %s)")
        params += [like_pattern(q)] * 2
    if role:
        conditions.append("r.role_name = %s")
        params.append(role)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    base = "FROM MEMBERS m INNER JOIN ROLES r ON r.role_id = m.role_id" + where

    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS n " + base, params).fetchone()["n"]
    pg = Pagination(get_page(), 15, total)
    rows = conn.execute(
        "SELECT m.member_id, m.full_name, m.email, m.phone, m.joined_at, r.role_name, "
        "  (SELECT COUNT(*) FROM BOOK_ISSUES i WHERE i.member_id = m.member_id "
        "     AND i.return_date IS NULL) AS open_loans "
        + base + " ORDER BY m.full_name LIMIT %s OFFSET %s",
        params + [pg.per_page, pg.offset],
    ).fetchall()
    return render_template("members/list.html", rows=rows, pg=pg, q=q, role=role, roles=_roles(conn))


@bp.route("/new", methods=["GET", "POST"])
@librarian_required
def new():
    conn = get_db()
    roles = _roles(conn)
    valid = {r["role_id"] for r in roles}
    form, errors = {}, {}
    if request.method == "POST":
        form = request.form
        data, errors = validate_member(form, valid, is_new=True)
        if not errors:
            data["password_hash"] = hash_password(data["password"])
            try:
                conn.execute(
                    "INSERT INTO MEMBERS (role_id, full_name, email, password_hash, phone) "
                    "VALUES (%(role_id)s, %(full_name)s, %(email)s, %(password_hash)s, %(phone)s)",
                    data)
                flash("Member added.", "success")
                return redirect(url_for("members.list_members"))
            except psycopg.errors.UniqueViolation:
                errors["email"] = "This e-mail address is already registered."
    return render_template("members/form.html", form=form, errors=errors, roles=roles, member=None)


@bp.route("/<int:member_id>/edit", methods=["GET", "POST"])
@librarian_required
def edit(member_id):
    conn = get_db()
    member = conn.execute("SELECT * FROM MEMBERS WHERE member_id = %s", (member_id,)).fetchone()
    if member is None:
        abort(404)
    roles = _roles(conn)
    valid = {r["role_id"] for r in roles}
    form, errors = member, {}
    if request.method == "POST":
        form = request.form
        data, errors = validate_member(form, valid, is_new=False)
        if not errors and member_id == g.user["member_id"] and data["role_id"] != member["role_id"]:
            errors["role_id"] = "You cannot change your own role."
        if not errors:
            data["member_id"] = member_id
            try:
                with conn.transaction():
                    conn.execute(
                        "UPDATE MEMBERS SET role_id = %(role_id)s, full_name = %(full_name)s, "
                        "email = %(email)s, phone = %(phone)s WHERE member_id = %(member_id)s", data)
                    if data["password"]:
                        conn.execute("UPDATE MEMBERS SET password_hash = %s WHERE member_id = %s",
                                     (hash_password(data["password"]), member_id))
                flash("Member updated.", "success")
                return redirect(url_for("members.list_members"))
            except psycopg.errors.UniqueViolation:
                errors["email"] = "This e-mail address is already registered."
    return render_template("members/form.html", form=form, errors=errors, roles=roles, member=member)


@bp.route("/<int:member_id>/history")
@librarian_required
def history(member_id):
    conn = get_db()
    member = conn.execute(
        "SELECT m.member_id, m.full_name, m.email, r.role_name FROM MEMBERS m "
        "INNER JOIN ROLES r ON r.role_id = m.role_id WHERE m.member_id = %s", (member_id,)).fetchone()
    if member is None:
        abort(404)
    rows = conn.execute(
        "SELECT * FROM v_student_issue_history WHERE member_id = %s "
        "ORDER BY issue_date DESC, issue_id DESC", (member_id,)).fetchall()
    return render_template("members/history.html", member=member, rows=rows,
                           total_balance=sum(r["fine_balance"] for r in rows))
