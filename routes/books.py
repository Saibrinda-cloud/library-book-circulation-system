"""Module 2 (book management) and the book-search half of Module 5."""
import psycopg
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import get_db
from security import librarian_required, login_required
from utils import Pagination, get_page, like_pattern
from validation import validate_book

bp = Blueprint("books", __name__, url_prefix="/books")

BOOK_COLUMNS = ("a.*, r.review_count, r.average_rating")
BOOK_FROM = ("FROM v_book_availability a "
             "LEFT JOIN v_book_review_summary r ON r.book_id = a.book_id")


@bp.route("/")
@login_required
def list_books():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    only_available = request.args.get("available") == "1"

    conditions, params = [], []
    if q:
        pattern = like_pattern(q)
        conditions.append("(a.title ILIKE %s OR a.author ILIKE %s OR a.category ILIKE %s "
                          "OR a.isbn ILIKE %s)")
        params += [pattern] * 4
    if category:
        conditions.append("a.category = %s")
        params.append(category)
    if only_available:
        conditions.append("a.available_copies > 0")
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS n " + BOOK_FROM + where, params).fetchone()["n"]
    pg = Pagination(get_page(), 12, total)
    rows = conn.execute(
        f"SELECT {BOOK_COLUMNS} {BOOK_FROM}{where} ORDER BY a.title LIMIT %s OFFSET %s",
        params + [pg.per_page, pg.offset],
    ).fetchall()
    categories = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM BOOKS ORDER BY category").fetchall()]
    return render_template("books/list.html", rows=rows, pg=pg, q=q, category=category,
                           only_available=only_available, categories=categories)


@bp.route("/<int:book_id>")
@login_required
def detail(book_id):
    conn = get_db()
    book = conn.execute(f"SELECT {BOOK_COLUMNS} {BOOK_FROM} WHERE a.book_id = %s",
                        (book_id,)).fetchone()
    if book is None:
        abort(404)
    reviews = conn.execute(
        "SELECT r.rating, r.review_text, r.review_date, m.full_name "
        "FROM BOOK_REVIEWS r INNER JOIN MEMBERS m ON m.member_id = r.member_id "
        "WHERE r.book_id = %s ORDER BY r.review_date DESC, r.review_id DESC",
        (book_id,),
    ).fetchall()
    has_reviewed = False
    if g.user["role_name"] == "Student":
        has_reviewed = conn.execute(
            "SELECT 1 FROM BOOK_REVIEWS WHERE member_id = %s AND book_id = %s",
            (g.user["member_id"], book_id),
        ).fetchone() is not None
    return render_template("books/detail.html", book=book, reviews=reviews,
                           has_reviewed=has_reviewed, errors={}, form={})


def _categories(conn):
    return [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM BOOKS ORDER BY category").fetchall()]


@bp.route("/new", methods=["GET", "POST"])
@librarian_required
def new():
    conn = get_db()
    form, errors = {"total_copies": "1", "damaged_copies": "0"}, {}
    if request.method == "POST":
        form = request.form
        data, errors = validate_book(form)
        if not errors:
            try:
                row = conn.execute(
                    "INSERT INTO BOOKS (isbn, title, author, category, publisher, "
                    "publication_year, total_copies, damaged_copies) "
                    "VALUES (%(isbn)s, %(title)s, %(author)s, %(category)s, %(publisher)s, "
                    "%(publication_year)s, %(total_copies)s, %(damaged_copies)s) RETURNING book_id",
                    data,
                ).fetchone()
                flash("Book added.", "success")
                return redirect(url_for("books.detail", book_id=row["book_id"]))
            except psycopg.errors.UniqueViolation:
                errors["isbn"] = "Another book already uses this ISBN."
    return render_template("books/form.html", form=form, errors=errors, book=None,
                           categories=_categories(conn))


@bp.route("/<int:book_id>/edit", methods=["GET", "POST"])
@librarian_required
def edit(book_id):
    conn = get_db()
    book = conn.execute("SELECT * FROM BOOKS WHERE book_id = %s", (book_id,)).fetchone()
    if book is None:
        abort(404)
    form, errors = book, {}
    if request.method == "POST":
        form = request.form
        data, errors = validate_book(form)
        if not errors:
            data["book_id"] = book_id
            try:
                with conn.transaction():
                    conn.execute("SELECT book_id FROM BOOKS WHERE book_id = %s FOR UPDATE", (book_id,))
                    on_loan = conn.execute(
                        "SELECT COUNT(*) AS n FROM BOOK_ISSUES "
                        "WHERE book_id = %s AND return_date IS NULL", (book_id,)).fetchone()["n"]
                    if data["total_copies"] - data["damaged_copies"] < on_loan:
                        errors["total_copies"] = (
                            f"{on_loan} copies are on loan, so total minus damaged copies "
                            f"cannot be below {on_loan}.")
                    else:
                        conn.execute(
                            "UPDATE BOOKS SET isbn = %(isbn)s, title = %(title)s, "
                            "author = %(author)s, category = %(category)s, "
                            "publisher = %(publisher)s, publication_year = %(publication_year)s, "
                            "total_copies = %(total_copies)s, damaged_copies = %(damaged_copies)s "
                            "WHERE book_id = %(book_id)s", data)
                if not errors:
                    flash("Book updated.", "success")
                    return redirect(url_for("books.detail", book_id=book_id))
            except psycopg.errors.UniqueViolation:
                errors["isbn"] = "Another book already uses this ISBN."
    return render_template("books/form.html", form=form, errors=errors, book=book,
                           categories=_categories(conn))


@bp.route("/<int:book_id>/delete", methods=["POST"])
@librarian_required
def delete(book_id):
    try:
        row = get_db().execute("DELETE FROM BOOKS WHERE book_id = %s RETURNING title",
                               (book_id,)).fetchone()
    except psycopg.errors.RestrictViolation:
        flash("This book has issue or review records, so it cannot be deleted.", "error")
        return redirect(url_for("books.detail", book_id=book_id))
    if row is None:
        abort(404)
    flash(f"Deleted \u201c{row['title']}\u201d.", "success")
    return redirect(url_for("books.list_books"))
