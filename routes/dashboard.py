"""Landing pages: librarian overview, student overview and the student's own history."""
from flask import Blueprint, g, render_template

from db import get_db
from security import login_required, student_required

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def home():
    conn = get_db()
    if g.user["role_name"] == "Librarian":
        stats = conn.execute(
            "SELECT (SELECT COUNT(*) FROM BOOKS) AS titles, "
            "       (SELECT COALESCE(SUM(total_copies), 0) FROM BOOKS) AS copies, "
            "       (SELECT COUNT(*) FROM BOOK_ISSUES WHERE return_date IS NULL) AS on_loan, "
            "       (SELECT COUNT(*) FROM v_overdue_books) AS overdue, "
            "       (SELECT COALESCE(SUM(amount - amount_paid), 0) FROM FINES) AS outstanding, "
            "       (SELECT COUNT(*) FROM MEMBERS m INNER JOIN ROLES r ON r.role_id = m.role_id "
            "         WHERE r.role_name = 'Student') AS students"
        ).fetchone()
        late = conn.execute(
            "SELECT issue_id, member_name, title, due_date, days_overdue "
            "FROM v_overdue_books ORDER BY days_overdue DESC LIMIT 5"
        ).fetchall()
        return render_template("dashboard_librarian.html", stats=stats, late=late)

    # Student: every query below is limited to the member id stored in the session.
    stats = conn.execute(
        "SELECT COUNT(*) FILTER (WHERE return_date IS NULL) AS on_loan, "
        "       COUNT(*) FILTER (WHERE days_overdue > 0) AS overdue, "
        "       COALESCE(SUM(fine_balance), 0) AS fine_balance "
        "FROM v_student_issue_history WHERE member_id = %s",
        (g.user["member_id"],),
    ).fetchone()
    loans = conn.execute(
        "SELECT issue_id, book_id, title, author, issue_date, due_date, days_overdue "
        "FROM v_student_issue_history WHERE member_id = %s AND return_date IS NULL "
        "ORDER BY due_date",
        (g.user["member_id"],),
    ).fetchall()
    return render_template("dashboard_student.html", stats=stats, loans=loans)


@bp.route("/my/history")
@student_required
def my_history():
    rows = get_db().execute(
        "SELECT * FROM v_student_issue_history WHERE member_id = %s "
        "ORDER BY issue_date DESC, issue_id DESC",
        (g.user["member_id"],),
    ).fetchall()
    total_balance = sum(r["fine_balance"] for r in rows)
    return render_template("my_history.html", rows=rows, total_balance=total_balance)
