"""Module 3: issue and return of books."""
import psycopg
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

import services
from db import get_db
from security import librarian_required
from services import RuleViolation
from utils import Pagination, get_page, like_pattern, to_int

bp = Blueprint("circulation", __name__, url_prefix="/circulation")


@bp.route("/")
@librarian_required
def list_issues():
    status = request.args.get("status", "open")
    q = request.args.get("q", "").strip()
    conditions, params = [], []
    if status == "open":
        conditions.append("return_date IS NULL")
    elif status == "overdue":
        conditions.append("days_overdue > 0")
    elif status == "returned":
        conditions.append("return_date IS NOT NULL")
    else:
        status = "all"
    if q:
        conditions.append("(member_name ILIKE %s OR title ILIKE %s)")
        params += [like_pattern(q)] * 2
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS n FROM v_librarian_issue_report" + where,
                         params).fetchone()["n"]
    pg = Pagination(get_page(), 15, total)
    rows = conn.execute(
        "SELECT * FROM v_librarian_issue_report" + where +
        " ORDER BY (return_date IS NULL) DESC, due_date, issue_id LIMIT %s OFFSET %s",
        params + [pg.per_page, pg.offset]).fetchall()
    return render_template("circulation/list.html", rows=rows, pg=pg, status=status, q=q)


@bp.route("/issue", methods=["GET", "POST"])
@librarian_required
def issue():
    conn = get_db()
    if request.method == "POST":
        member_id = to_int(request.form.get("member_id"))
        book_id = to_int(request.form.get("book_id"))
        if member_id is None or book_id is None:
            flash("Choose both a student and a book.", "error")
        else:
            try:
                book, member, row = services.issue_book(
                    conn, member_id, book_id, current_app.config["LOAN_PERIOD_DAYS"])
                flash(f"Issued \u201c{book['title']}\u201d to {member['full_name']}. "
                      f"Due on {row['due_date']:%d %b %Y}.", "success")
                return redirect(url_for("circulation.list_issues"))
            except RuleViolation as exc:
                flash(str(exc), "error")
            except psycopg.errors.UniqueViolation:
                flash("This student already has an unreturned copy of that book.", "error")
    students = conn.execute(
        "SELECT m.member_id, m.full_name, m.email FROM MEMBERS m "
        "INNER JOIN ROLES r ON r.role_id = m.role_id WHERE r.role_name = 'Student' "
        "ORDER BY m.full_name").fetchall()
    books = conn.execute(
        "SELECT book_id, title, author, available_copies FROM v_book_availability "
        "WHERE available_copies > 0 ORDER BY title").fetchall()
    return render_template("circulation/issue.html", students=students, books=books)


@bp.route("/<int:issue_id>/return", methods=["POST"])
@librarian_required
def return_book(issue_id):
    conn = get_db()
    try:
        issue, days_late, fine = services.return_book(
            conn, issue_id, current_app.config["FINE_PER_DAY"])
    except RuleViolation as exc:
        flash(str(exc), "error")
    except psycopg.Error:
        current_app.logger.exception("Return failed for issue %s", issue_id)
        flash("The return could not be completed, so nothing was saved. Please try again.", "error")
    else:
        if fine:
            flash(f"Returned \u201c{issue['title']}\u201d {days_late} day(s) late. "
                  f"Fine of Rs. {fine['amount']:,.2f} recorded for {issue['full_name']}.", "info")
        else:
            flash(f"Returned \u201c{issue['title']}\u201d from {issue['full_name']} on time.", "success")
    return redirect(request.referrer or url_for("circulation.list_issues"))
