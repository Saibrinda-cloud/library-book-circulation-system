"""Module 6: book reviews (students submit one review per book)."""
import psycopg
from flask import Blueprint, abort, flash, g, redirect, url_for, request

from db import get_db
from security import student_required
from validation import validate_review

bp = Blueprint("reviews", __name__)


@bp.route("/books/<int:book_id>/review", methods=["POST"])
@student_required
def submit(book_id):
    conn = get_db()
    if conn.execute("SELECT 1 FROM BOOKS WHERE book_id = %s", (book_id,)).fetchone() is None:
        abort(404)
    data, errors = validate_review(request.form)
    if errors:
        flash(" ".join(errors.values()), "error")
    else:
        try:
            conn.execute(
                "INSERT INTO BOOK_REVIEWS (member_id, book_id, rating, review_text) "
                "VALUES (%s, %s, %s, %s)",
                (g.user["member_id"], book_id, data["rating"], data["review_text"]),
            )
            flash("Thank you. Your review has been saved.", "success")
        except psycopg.errors.UniqueViolation:
            flash("You have already reviewed this book.", "error")
    return redirect(url_for("books.detail", book_id=book_id))
