"""Module 5: reports. Popularity and review summaries are open to all logged-in users;
everything else is librarian-only."""
from flask import Blueprint, current_app, render_template

from db import get_db
from security import librarian_required, login_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


def table(title, intro, columns, rows, **extra):
    """columns: list of (key, heading, kind); kind drives formatting in reports/table.html."""
    return render_template("reports/table.html", title=title, intro=intro,
                           columns=columns, rows=rows, **extra)


@bp.route("/")
@librarian_required
def index():
    conn = get_db()
    by_category = conn.execute(
        "SELECT b.category, COUNT(DISTINCT b.book_id) AS titles, SUM(b.total_copies) AS copies, "
        "       COUNT(i.issue_id) AS times_issued "
        "FROM BOOKS b LEFT JOIN BOOK_ISSUES i ON i.book_id = b.book_id "
        "GROUP BY b.category ORDER BY times_issued DESC, b.category").fetchall()
    return render_template("reports/index.html", by_category=by_category)


@bp.route("/overdue")
@librarian_required
def overdue():
    rate = current_app.config["FINE_PER_DAY"]
    rows = get_db().execute(
        "SELECT issue_id, member_name, member_email, title, due_date, days_overdue, "
        "       days_overdue * %s::numeric AS fine_if_returned_today "
        "FROM v_overdue_books ORDER BY days_overdue DESC, issue_id", (rate,)).fetchall()
    return table(
        "Overdue books",
        "Unreturned books past their due date. The projected fine is days overdue \u00d7 "
        f"Rs. {rate} and is only recorded when the book is returned.",
        [("member_name", "Member", "text"), ("member_email", "E-mail", "text"),
         ("title", "Book", "text"), ("due_date", "Due date", "date"),
         ("days_overdue", "Days overdue", "int"), ("fine_if_returned_today", "Fine if returned today", "money")],
        rows)


@bp.route("/fines")
@librarian_required
def fines():
    conn = get_db()
    summary = conn.execute(
        "SELECT COUNT(*) AS fines_recorded, COALESCE(SUM(amount), 0) AS total_fined, "
        "COALESCE(SUM(amount_paid), 0) AS total_collected, "
        "COALESCE(SUM(amount - amount_paid), 0) AS total_outstanding, "
        "AVG(amount) AS average_fine, MIN(amount) AS smallest_fine, MAX(amount) AS largest_fine "
        "FROM FINES").fetchone()
    by_status = conn.execute(
        "SELECT status, COUNT(*) AS fines, SUM(amount) AS fined, SUM(amount_paid) AS collected, "
        "SUM(amount - amount_paid) AS outstanding FROM FINES GROUP BY status "
        "ORDER BY status").fetchall()
    outstanding = conn.execute(
        "SELECT member_name, title, amount, amount_paid, balance, status "
        "FROM v_outstanding_fines ORDER BY balance DESC").fetchall()
    return render_template("reports/fines.html", summary=summary, by_status=by_status,
                           outstanding=outstanding)


@bp.route("/popular")
@login_required
def popular():
    rows = get_db().execute(
        "SELECT b.title, b.author, b.category, COUNT(i.issue_id) AS times_issued, "
        "       s.review_count, s.average_rating "
        "FROM BOOKS b "
        "LEFT JOIN BOOK_ISSUES i ON i.book_id = b.book_id "
        "LEFT JOIN v_book_review_summary s ON s.book_id = b.book_id "
        "GROUP BY b.book_id, s.review_count, s.average_rating "
        "ORDER BY times_issued DESC, b.title LIMIT 10").fetchall()
    return table("Most borrowed books", "The ten books issued most often, with their review summary.",
                 [("title", "Book", "text"), ("author", "Author", "text"),
                  ("category", "Category", "text"), ("times_issued", "Times issued", "int"),
                  ("review_count", "Reviews", "int"), ("average_rating", "Average rating", "rating")], rows)


@bp.route("/reviews")
@login_required
def reviews():
    rows = get_db().execute(
        "SELECT title, author, review_count, average_rating FROM v_book_review_summary "
        "ORDER BY average_rating DESC NULLS LAST, review_count DESC, title").fetchall()
    return table("Book review summary",
                 "Every book with its number of reviews and average rating. Books without reviews are listed last.",
                 [("title", "Book", "text"), ("author", "Author", "text"),
                  ("review_count", "Reviews", "int"), ("average_rating", "Average rating", "rating")], rows)


@bp.route("/follow-up")
@librarian_required
def follow_up():
    rows = get_db().execute(
        "SELECT m.member_id, m.full_name, m.email, 'Overdue book' AS reason "
        "FROM MEMBERS m INNER JOIN BOOK_ISSUES i ON i.member_id = m.member_id "
        "WHERE i.return_date IS NULL AND i.due_date < CURRENT_DATE "
        "UNION "
        "SELECT m.member_id, m.full_name, m.email, 'Unpaid fine' "
        "FROM MEMBERS m INNER JOIN BOOK_ISSUES i ON i.member_id = m.member_id "
        "INNER JOIN FINES f ON f.issue_id = i.issue_id WHERE f.amount > f.amount_paid "
        "ORDER BY full_name, reason").fetchall()
    return table("Members needing follow-up",
                 "Members with an overdue book or an unpaid fine (a UNION of two queries). "
                 "A member with both appears twice, once per reason.",
                 [("full_name", "Member", "text"), ("email", "E-mail", "text"), ("reason", "Reason", "text")], rows)


@bp.route("/members")
@librarian_required
def members():
    rows = get_db().execute(
        "SELECT m.full_name, m.email, COUNT(i.issue_id) AS total_issues, "
        "       COUNT(i.issue_id) FILTER (WHERE i.return_date IS NULL) AS on_loan "
        "FROM MEMBERS m INNER JOIN ROLES r ON r.role_id = m.role_id "
        "LEFT JOIN BOOK_ISSUES i ON i.member_id = m.member_id "
        "WHERE r.role_name = 'Student' GROUP BY m.member_id "
        "ORDER BY total_issues DESC, m.full_name").fetchall()
    return table("Borrowing per student",
                 "All students, including those who have never borrowed (a LEFT JOIN).",
                 [("full_name", "Student", "text"), ("email", "E-mail", "text"),
                  ("total_issues", "Total issues", "int"), ("on_loan", "On loan now", "int")], rows)
