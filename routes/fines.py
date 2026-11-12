"""Module 4: fine balances and payments recorded by the librarian."""
import psycopg
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

import services
from db import get_db
from security import librarian_required
from services import RuleViolation
from utils import Pagination, get_page, like_pattern
from validation import parse_money

bp = Blueprint("fines", __name__, url_prefix="/fines")


@bp.route("/")
@librarian_required
def list_fines():
    status = request.args.get("status", "outstanding")
    q = request.args.get("q", "").strip()
    conditions, params = [], []
    if status == "outstanding":
        conditions.append("f.amount - f.amount_paid > 0")
    elif status == "paid":
        conditions.append("f.status = 'Paid'")
    else:
        status = "all"
    if q:
        conditions.append("(m.full_name ILIKE %s OR b.title ILIKE %s)")
        params += [like_pattern(q)] * 2
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    base = ("FROM FINES f "
            "INNER JOIN BOOK_ISSUES i ON i.issue_id = f.issue_id "
            "INNER JOIN MEMBERS m ON m.member_id = i.member_id "
            "INNER JOIN BOOKS b ON b.book_id = i.book_id" + where)

    conn = get_db()
    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS fined, COALESCE(SUM(amount_paid), 0) AS collected, "
        "COALESCE(SUM(amount - amount_paid), 0) AS outstanding FROM FINES").fetchone()
    total = conn.execute("SELECT COUNT(*) AS n " + base, params).fetchone()["n"]
    pg = Pagination(get_page(), 15, total)
    rows = conn.execute(
        "SELECT f.issue_id, m.member_id, m.full_name, b.title, i.due_date, i.return_date, "
        "f.amount, f.amount_paid, f.amount - f.amount_paid AS balance, f.status, f.created_at "
        + base + " ORDER BY balance DESC, f.created_at DESC LIMIT %s OFFSET %s",
        params + [pg.per_page, pg.offset]).fetchall()
    return render_template("fines/list.html", rows=rows, pg=pg, status=status, q=q, totals=totals)


@bp.route("/<int:issue_id>/pay", methods=["POST"])
@librarian_required
def pay(issue_id):
    payment = parse_money(request.form.get("payment"))
    if payment is None:
        flash("Enter a payment greater than zero with at most two decimal places.", "error")
    else:
        try:
            row = services.record_payment(get_db(), issue_id, payment)
            flash(f"Recorded Rs. {payment:,.2f}. Fine status: {row['status']}, "
                  f"balance Rs. {row['amount'] - row['amount_paid']:,.2f}.", "success")
        except RuleViolation as exc:
            flash(str(exc), "error")
        except psycopg.Error:
            current_app.logger.exception("Payment failed for issue %s", issue_id)
            flash("The payment could not be saved. Please try again.", "error")
    return redirect(request.referrer or url_for("fines.list_fines"))
