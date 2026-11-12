"""Automated smoke test using Flask's test client against a SCRATCH database.

    1. Create the scratch database once (sql/create_database.sql already does this):
           CREATE DATABASE library_test OWNER lms_user;
    2. Run:   python smoke_test.py            (uses database "library_test")
              python smoke_test.py --db my_other_test

The script REBUILDS the scratch database (drops and recreates all tables) on every run.
For safety it refuses any database name that does not end in "_test".
"""
import argparse
import os
import re
import sys
import threading
from decimal import Decimal

parser = argparse.ArgumentParser()
parser.add_argument("--db", default="library_test")
args = parser.parse_args()
if not args.db.endswith("_test"):
    sys.exit("Refusing to run: the database name must end with '_test' (it will be wiped).")
os.environ["DB_NAME"] = args.db
os.environ.setdefault("SECRET_KEY", "smoke-test-secret-key-not-for-real-use-0123456789")

import psycopg                                   # noqa: E402
from psycopg.rows import dict_row                # noqa: E402

import services                                  # noqa: E402
import setup_db                                  # noqa: E402
from app import create_app                       # noqa: E402
from config import Config                        # noqa: E402

results = []


def check(name, condition, detail=""):
    results.append((bool(condition), name))
    print(("PASS  " if condition else "FAIL  ") + name + ("" if condition else f"   <-- {detail}"))


def connect():
    return psycopg.connect(host=Config.DB_HOST, port=Config.DB_PORT, dbname=Config.DB_NAME,
                           user=Config.DB_USER, password=Config.DB_PASSWORD,
                           autocommit=True, row_factory=dict_row)


DB = None


def q(sql, params=None):
    return DB.execute(sql, params).fetchall()


def q1(sql, params=None):
    return DB.execute(sql, params).fetchone()


def member_id(email):
    return q1("SELECT member_id FROM MEMBERS WHERE email = %s", (email,))["member_id"]


def book_id(title):
    return q1("SELECT book_id FROM BOOKS WHERE title = %s", (title,))["book_id"]


def issue_id(email, title, open_only=True):
    row = q1("SELECT i.issue_id FROM BOOK_ISSUES i JOIN MEMBERS m USING (member_id) "
             "JOIN BOOKS b USING (book_id) WHERE m.email = %s AND b.title = %s "
             + ("AND i.return_date IS NULL " if open_only else "") + "ORDER BY i.issue_id DESC",
             (email, title))
    return row["issue_id"] if row else None


def page(client, url, **kw):
    return client.get(url, follow_redirects=True, **kw)


def post(client, url, data=None, follow=True):
    with client.session_transaction() as s:
        s["_csrf"] = "test-token"
    payload = dict(data or {})
    payload["_csrf"] = "test-token"
    return client.post(url, data=payload, follow_redirects=follow)


def login(app, email, password):
    c = app.test_client()
    c.get("/login")
    r = post(c, "/login", {"email": email, "password": password}, follow=False)
    return c, r


LIB = "meera.nair@college.example"
ARJUN = "arjun.kumar@college.example"
SNEHA = "sneha.iyer@college.example"
KARTHIK = "karthik.rao@college.example"


def main():
    global DB
    print(f"Rebuilding scratch database '{args.db}' ...")
    setup_db.build(reset=True)
    DB = connect()
    app = create_app({"TESTING": True, "PROPAGATE_EXCEPTIONS": False})

    # ------------------------------------------------------------ seed data integrity
    print("\n-- Database and seed data")
    counts = {t: q1(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in
              ("ROLES", "MEMBERS", "BOOKS", "BOOK_ISSUES", "FINES", "BOOK_REVIEWS")}
    check("six tables exist and are populated", all(n > 0 for n in counts.values()), counts)
    bad = q1("SELECT COUNT(*) AS n FROM FINES f JOIN BOOK_ISSUES i USING (issue_id) "
             "WHERE f.amount <> (i.return_date - i.due_date) * 2.00")["n"]
    check("seed fines equal overdue days x Rs. 2", bad == 0)
    check("no book has negative availability",
          q1("SELECT COUNT(*) AS n FROM v_book_availability WHERE available_copies < 0")["n"] == 0)
    check("password hashes are not plaintext",
          q1("SELECT COUNT(*) AS n FROM MEMBERS WHERE password_hash LIKE 'pbkdf2:sha256:%'")["n"] == counts["MEMBERS"])

    print("\n-- Database constraints reject invalid data")
    def rejected(sql, params, exc):
        try:
            DB.execute(sql, params)
            return False
        except exc:
            return True
    check("rating 7 rejected (CHECK)", rejected(
        "INSERT INTO BOOK_REVIEWS (member_id, book_id, rating) VALUES (%s, %s, 7)",
        (member_id(KARTHIK), book_id("Gitanjali")), psycopg.errors.CheckViolation))
    check("damaged copies > total rejected (CHECK)", rejected(
        "INSERT INTO BOOKS (title, author, category, total_copies, damaged_copies) "
        "VALUES ('x','y','z',1,2)", None, psycopg.errors.CheckViolation))
    check("issue for a missing member rejected (FK)", rejected(
        "INSERT INTO BOOK_ISSUES (member_id, book_id, due_date) VALUES (99999, %s, CURRENT_DATE)",
        (book_id("Gitanjali"),), psycopg.errors.ForeignKeyViolation))
    check("deleting a book that has issues refused (FK RESTRICT)", rejected(
        "DELETE FROM BOOKS WHERE title = 'Clean Code'", None, psycopg.errors.RestrictViolation))
    check("duplicate review rejected (UNIQUE member, book)", rejected(
        "INSERT INTO BOOK_REVIEWS (member_id, book_id, rating) VALUES (%s, %s, 4)",
        (member_id(ARJUN), book_id("Database System Concepts")), psycopg.errors.UniqueViolation))
    check("fine with inconsistent status rejected (CHECK)", rejected(
        "INSERT INTO FINES (issue_id, amount, amount_paid, status) VALUES (%s, 10, 5, 'Paid')",
        (issue_id(ARJUN, "Operating System Concepts"),), psycopg.errors.CheckViolation))
    DB.execute("INSERT INTO BOOKS (title, author, category, total_copies) VALUES ('NoIsbn1','a','c',1),('NoIsbn2','a','c',1)")
    check("two books with NULL ISBN allowed", True)

    # ------------------------------------------------------------ login / roles
    print("\n-- Module 1: login and role management")
    anon = app.test_client()
    check("login page loads", anon.get("/login").status_code == 200)
    r = anon.get("/books/", follow_redirects=False)
    check("anonymous user redirected to login", r.status_code == 302 and "/login" in r.headers["Location"])
    c, r = login(app, ARJUN, "wrong-password")
    check("wrong password refused", r.status_code == 200 and b"Incorrect e-mail or password" in r.data)
    c, r = login(app, "nobody@college.example", "Student@123")
    check("unknown e-mail refused with same message", b"Incorrect e-mail or password" in r.data)
    c, r = login(app, "' OR '1'='1", "' OR '1'='1")
    check("SQL-injection style login refused", b"Incorrect e-mail or password" in r.data)
    student, r = login(app, ARJUN, "Student@123")
    check("student login redirects to dashboard", r.status_code == 302 and "/dashboard" in r.headers["Location"])
    check("student dashboard shows own name", b"Welcome, Arjun" in page(student, "/dashboard").data)
    lib, r = login(app, LIB, "Librarian@123")
    check("librarian login works", b"Circulation desk" in page(lib, "/dashboard").data)
    check("logout without CSRF token refused (400)", lib.post("/logout").status_code == 400)
    tmp, _ = login(app, LIB, "Librarian@123")
    r = post(tmp, "/logout")
    check("logout ends the session", b"Log in" in r.data and page(tmp, "/books/").request.path == "/login")

    print("\n-- Role-based access (enforced on the server)")
    for url in ("/members/", "/circulation/", "/circulation/issue", "/fines/", "/reports/",
                "/reports/overdue", "/books/new", "/members/new"):
        check(f"student blocked from {url} (403)", student.get(url).status_code == 403)
    other = issue_id("faizan.ahmed@college.example", "Clean Code")
    check("student cannot POST a return (403)",
          post(student, f"/circulation/{other}/return", follow=False).status_code == 403)
    check("student cannot POST a payment (403)",
          post(student, f"/fines/{issue_id(SNEHA, 'Fundamentals of Database Systems', False)}/pay",
               {"payment": "5"}, follow=False).status_code == 403)
    check("student cannot delete a book (403)",
          post(student, f"/books/{book_id('Gitanjali')}/delete", follow=False).status_code == 403)
    check("librarian blocked from student-only page (403)", lib.get("/my/history").status_code == 403)
    check("student can open catalogue (HTTP 200)", student.get("/books/").status_code == 200)
    check("student can open popular books (HTTP 200)", student.get("/reports/popular").status_code == 200)
    check("student can open review summary (HTTP 200)", student.get("/reports/reviews").status_code == 200)
    check("catalogue pagination: page 2 opens", student.get("/books/?page=2").status_code == 200)
    check("student pages render: dashboard, history, book detail",
          all(student.get(u).status_code == 200 for u in ("/dashboard", "/my/history", f"/books/{book_id('Atomic Habits')}")))
    check("librarian pages render: forms and detail pages",
          all(lib.get(u).status_code == 200 for u in ("/books/new", "/members/new", "/circulation/issue",
              f"/books/{book_id('Atomic Habits')}/edit", f"/members/{member_id(ARJUN)}/edit",
              f"/books/{book_id('Atomic Habits')}", "/circulation/?status=all", "/fines/?status=all")))

    print("\n-- Student sees only own records")
    mine = page(student, "/my/history")
    check("own loan shown", b"Operating System Concepts" in mine.data)
    check("another student's loan not shown", b"Train to Pakistan" not in mine.data)
    spoof = page(student, f"/my/history?member_id={member_id(SNEHA)}")
    check("member_id in the URL is ignored", b"Train to Pakistan" not in spoof.data)
    check("student cannot open a member's history page",
          student.get(f"/members/{member_id(SNEHA)}/history").status_code == 403)
    check("librarian can open a member's history",
          b"Train to Pakistan" in page(lib, f"/members/{member_id(SNEHA)}/history").data)

    # ------------------------------------------------------------ books and search
    print("\n-- Module 2 and 5: books and search")
    r = post(lib, "/books/new", {"title": "Smoke Test Book", "author": "T. Ester", "category": "Testing",
                                 "isbn": "978-1-23-456789-0", "publisher": "", "publication_year": "2020",
                                 "total_copies": "2", "damaged_copies": "0"})
    check("librarian adds a book", b"Book added" in r.data)
    check("book saved in database", q1("SELECT 1 AS x FROM BOOKS WHERE title = 'Smoke Test Book'") is not None)
    r = post(lib, "/books/new", {"title": "Bad", "author": "A", "category": "C", "total_copies": "1",
                                 "damaged_copies": "3"})
    check("damaged > total rejected by the form", b"cannot exceed total copies" in r.data)
    r = post(lib, "/books/new", {"title": "Bad", "author": "A", "category": "C", "total_copies": "-1",
                                 "damaged_copies": "0"})
    check("negative copies rejected", b"between 0 and" in r.data)
    r = post(lib, "/books/new", {"title": "Dup", "author": "A", "category": "C", "isbn": "978-1-23-456789-0",
                                 "total_copies": "1", "damaged_copies": "0"})
    check("duplicate ISBN rejected", b"already uses this ISBN" in r.data)
    sid = book_id("Smoke Test Book")
    r = post(lib, f"/books/{sid}/edit", {"title": "Smoke Test Book 2", "author": "T. Ester", "category": "Testing",
                                         "isbn": "978-1-23-456789-0", "total_copies": "3", "damaged_copies": "1"})
    check("librarian updates a book", b"Book updated" in r.data and
          q1("SELECT total_copies FROM BOOKS WHERE book_id = %s", (sid,))["total_copies"] == 3)
    cc = book_id("Clean Code")
    r = post(lib, f"/books/{cc}/edit", {"title": "Clean Code", "author": "Robert C. Martin", "category": "Computer Science",
                                        "total_copies": "1", "damaged_copies": "1"})
    check("cannot mark a copy damaged while it is on loan", b"on loan" in r.data)
    check("student can search case-insensitively", b"Database System Concepts" in page(student, "/books/?q=DATABASE").data)
    check("search by author works", b"Elmasri" in page(student, "/books/?q=elmasri").data)
    check("'available only' hides fully issued books", b"Clean Code" not in page(student, "/books/?available=1&q=clean").data)
    check("search with no match shows a message", b"No books match" in page(student, "/books/?q=zzzzqqq").data)
    check("LIKE wildcard % is matched literally", b"No books match" in page(student, "/books/?q=%25").data)
    check("injection-style search is harmless", b"No books match" in page(student, "/books/?q=%27%3B+DROP+TABLE+books%3B--").data)
    r = post(lib, f"/books/{sid}/delete")
    check("librarian deletes an unused book", b"Deleted" in r.data and
          q1("SELECT 1 AS x FROM BOOKS WHERE book_id = %s", (sid,)) is None)
    r = post(lib, f"/books/{cc}/delete")
    check("book with history cannot be deleted", b"cannot be deleted" in r.data and
          q1("SELECT 1 AS x FROM BOOKS WHERE book_id = %s", (cc,)) is not None)
    check("unknown book gives 404", student.get("/books/999999").status_code == 404)

    # ------------------------------------------------------------ members
    print("\n-- Module 1: member management")
    r = post(lib, "/members/new", {"full_name": "Test Student", "email": "Test.Student@college.example",
                                   "phone": "9111111111", "role_id": q1("SELECT role_id FROM ROLES WHERE role_name='Student'")["role_id"],
                                   "password": "Passw0rd!x"})
    check("librarian adds a member", b"Member added" in r.data)
    c2, r = login(app, "test.student@college.example", "Passw0rd!x")
    check("new member can log in (e-mail stored lower-case)", r.status_code == 302)
    r = post(lib, "/members/new", {"full_name": "Dup", "email": ARJUN, "role_id": "2", "password": "Passw0rd!x"})
    check("duplicate e-mail rejected", b"already registered" in r.data)
    r = post(lib, "/members/new", {"full_name": "Short", "email": "s@college.example", "role_id": "2", "password": "abc"})
    check("short password rejected", b"at least 8 characters" in r.data)
    r = post(lib, f"/members/{member_id(LIB)}/edit", {"full_name": "Meera Nair", "email": LIB,
                                                      "role_id": "2", "password": ""})
    check("librarian cannot change own role", b"cannot change your own role" in r.data)

    # ------------------------------------------------------------ issue
    print("\n-- Module 3: issue and return")
    me, dsc = member_id("anitha.raj@college.example"), book_id("Introduction to the Theory of Computation")
    r = post(lib, "/circulation/issue", {"member_id": me, "book_id": dsc})
    row = q1("SELECT * FROM BOOK_ISSUES WHERE member_id = %s AND book_id = %s", (me, dsc))
    check("available book issued", b"Issued" in r.data and row is not None)
    check("due date is issue date + 14 days", row and (row["due_date"] - row["issue_date"]).days == 14)
    check("availability decreased by one",
          q1("SELECT available_copies FROM v_book_availability WHERE book_id = %s", (dsc,))["available_copies"] == 1)
    r = post(lib, "/circulation/issue", {"member_id": me, "book_id": dsc})
    check("same student cannot hold the same book twice", b"already has an unreturned copy" in r.data)
    before = q1("SELECT COUNT(*) AS n FROM BOOK_ISSUES")["n"]
    r = post(lib, "/circulation/issue", {"member_id": member_id(KARTHIK), "book_id": cc})
    check("unavailable book cannot be issued", b"available right now" in r.data)
    check("no row created for refused issue", q1("SELECT COUNT(*) AS n FROM BOOK_ISSUES")["n"] == before)
    r = post(lib, "/circulation/issue", {"member_id": member_id(LIB), "book_id": dsc})
    check("a librarian account cannot borrow", b"registered student" in r.data)
    r = post(lib, "/circulation/issue", {"member_id": "", "book_id": ""})
    check("empty issue form rejected", b"Choose both" in r.data)

    print("\n-- Concurrency: two simultaneous issues of the last copy")
    last = book_id("Clean Code")
    DB.execute("UPDATE BOOKS SET total_copies = 2 WHERE book_id = %s", (last,))   # one copy free now
    outcome, barrier = [], threading.Barrier(2)
    def worker(email):
        with psycopg.connect(host=Config.DB_HOST, port=Config.DB_PORT, dbname=Config.DB_NAME,
                             user=Config.DB_USER, password=Config.DB_PASSWORD,
                             autocommit=True, row_factory=dict_row) as conn:
            barrier.wait()
            try:
                services.issue_book(conn, member_id(email), last, 14)
                outcome.append("issued")
            except services.RuleViolation:
                outcome.append("refused")
    ts = [threading.Thread(target=worker, args=(e,)) for e in ("priya.nair@college.example", "anitha.raj@college.example")]
    [t.start() for t in ts]; [t.join() for t in ts]
    check("exactly one of two simultaneous issues succeeds", sorted(outcome) == ["issued", "refused"], outcome)
    check("availability is 0, never negative",
          q1("SELECT available_copies FROM v_book_availability WHERE book_id = %s", (last,))["available_copies"] == 0)

    # ------------------------------------------------------------ return and fines
    print("\n-- Module 3 and 4: return and fine generation")
    ontime = issue_id(ARJUN, "Operating System Concepts")
    r = post(lib, f"/circulation/{ontime}/return")
    check("on-time return recorded without a fine", b"on time" in r.data and
          q1("SELECT 1 AS x FROM FINES WHERE issue_id = %s", (ontime,)) is None)
    check("returning again is refused", b"already been returned" in post(lib, f"/circulation/{ontime}/return").data)
    late = issue_id(KARTHIK, "Database System Concepts")           # seeded: 11 days overdue
    r = post(lib, f"/circulation/{late}/return")
    fine = q1("SELECT * FROM FINES WHERE issue_id = %s", (late,))
    check("11 days overdue gives Rs. 22.00 fine", fine and fine["amount"] == Decimal("22.00"), fine)
    check("new fine is Unpaid with nothing paid", fine and fine["status"] == "Unpaid" and fine["amount_paid"] == 0)
    check("return_date is today", q1("SELECT return_date = CURRENT_DATE AS ok FROM BOOK_ISSUES WHERE issue_id = %s", (late,))["ok"])
    # boundary: due today -> no fine; due yesterday -> Rs. 2
    b1, b2 = book_id("Gitanjali"), book_id("The Guide")
    DB.execute("INSERT INTO BOOK_ISSUES (member_id, book_id, issue_date, due_date) VALUES (%s,%s,CURRENT_DATE-14,CURRENT_DATE)",
               (member_id("anitha.raj@college.example"), b1))
    DB.execute("INSERT INTO BOOK_ISSUES (member_id, book_id, issue_date, due_date) VALUES (%s,%s,CURRENT_DATE-15,CURRENT_DATE-1)",
               (member_id("anitha.raj@college.example"), b2))
    i_today, i_yest = issue_id("anitha.raj@college.example", "Gitanjali"), issue_id("anitha.raj@college.example", "The Guide")
    post(lib, f"/circulation/{i_today}/return"); post(lib, f"/circulation/{i_yest}/return")
    check("boundary: returned on the due date, no fine", q1("SELECT 1 AS x FROM FINES WHERE issue_id = %s", (i_today,)) is None)
    check("boundary: 1 day late, fine Rs. 2.00",
          q1("SELECT amount FROM FINES WHERE issue_id = %s", (i_yest,))["amount"] == Decimal("2.00"))

    print("\n-- Transaction rollback")
    victim = issue_id(SNEHA, "Train to Pakistan")                   # 6 days overdue
    app.config["FINE_PER_DAY"] = Decimal("99999999")               # forces a numeric overflow
    r = post(lib, f"/circulation/{victim}/return")
    app.config["FINE_PER_DAY"] = Decimal("2.00")
    check("failed fine insert shows an error", b"nothing was saved" in r.data)
    check("rollback: return_date still empty",
          q1("SELECT return_date FROM BOOK_ISSUES WHERE issue_id = %s", (victim,))["return_date"] is None)
    check("rollback: no fine row", q1("SELECT 1 AS x FROM FINES WHERE issue_id = %s", (victim,)) is None)
    post(lib, f"/circulation/{victim}/return")
    check("after fixing the rate the same return succeeds (Rs. 12.00)",
          q1("SELECT amount FROM FINES WHERE issue_id = %s", (victim,))["amount"] == Decimal("12.00"))

    print("\n-- Fine payments")
    fid = late                                                      # Rs. 22.00, unpaid
    r = post(lib, f"/fines/{fid}/pay", {"payment": "10"})
    f = q1("SELECT * FROM FINES WHERE issue_id = %s", (fid,))
    check("partial payment -> Partial, paid 10.00", f["status"] == "Partial" and f["amount_paid"] == Decimal("10.00"), f)
    r = post(lib, f"/fines/{fid}/pay", {"payment": "20"})
    check("payment above balance rejected", b"more than the outstanding balance" in r.data)
    for bad in ("0", "-5", "abc", "1.234", ""):
        r = post(lib, f"/fines/{fid}/pay", {"payment": bad})
        check(f"invalid payment '{bad}' rejected", b"greater than zero" in r.data)
    r = post(lib, f"/fines/{fid}/pay", {"payment": "12.00"})
    f = q1("SELECT * FROM FINES WHERE issue_id = %s", (fid,))
    check("final payment -> Paid, balance 0", f["status"] == "Paid" and f["amount_paid"] == f["amount"])
    check("paying a settled fine is refused", b"already paid in full" in post(lib, f"/fines/{fid}/pay", {"payment": "1"}).data)
    check("paying where no fine exists is refused",
          b"No fine exists" in post(lib, f"/fines/{issue_id('divya.menon@college.example', 'Introduction to Algorithms')}/pay", {"payment": "1"}).data)

    # ------------------------------------------------------------ reports
    print("\n-- Module 5: reports")
    for url, text in (("/reports/", b"Borrowing by category"), ("/reports/overdue", b"Overdue books"),
                      ("/reports/fines", b"Fine collection summary"), ("/reports/popular", b"Most borrowed"),
                      ("/reports/reviews", b"review summary"), ("/reports/follow-up", b"follow-up"),
                      ("/reports/members", b"Borrowing per student"), ("/circulation/?status=overdue", b"Issue and return"),
                      ("/fines/", b"Fines"), ("/members/", b"Members"), ("/books/", b"Books")):
        resp = page(lib, url)
        check(f"librarian can open {url} (HTTP 200)", resp.status_code == 200 and text in resp.data, resp.status_code)
    over = page(lib, "/reports/overdue").data
    check("overdue report lists unreturned late books", b"Rahul Sharma" in over and b"Computer Networks" in over)
    check("overdue report excludes returned books", b"Database System Concepts" not in over)

    # ------------------------------------------------------------ reviews
    print("\n-- Module 6: reviews")
    gid = book_id("The Discovery of India")
    r = post(student, f"/books/{gid}/review", {"rating": "4", "review_text": "Rich and readable."})
    check("student submits a review", b"review has been saved" in r.data and b"Rich and readable." in r.data)
    r = post(student, f"/books/{gid}/review", {"rating": "5", "review_text": "Again"})
    check("second review for the same book refused", b"already reviewed" in r.data)
    check("still only one review stored", q1("SELECT COUNT(*) AS n FROM BOOK_REVIEWS WHERE book_id = %s", (gid,))["n"] == 1)
    for bad in ("7", "0", "", "abc"):
        r = post(student, f"/books/{book_id('Gitanjali')}/review", {"rating": bad})
        check(f"invalid rating '{bad}' rejected", q1("SELECT COUNT(*) AS n FROM BOOK_REVIEWS WHERE book_id = %s", (book_id('Gitanjali'),))["n"] == 0)
    r = post(student, f"/books/{book_id('Gitanjali')}/review", {"rating": "3", "review_text": "x" * 1001})
    check("over-long review rejected", q1("SELECT COUNT(*) AS n FROM BOOK_REVIEWS WHERE book_id = %s", (book_id('Gitanjali'),))["n"] == 0)
    check("librarian cannot submit reviews (403)", post(lib, f"/books/{gid}/review", {"rating": "3"}, follow=False).status_code == 403)
    check("review for a missing book gives 404", post(student, "/books/999999/review", {"rating": "3"}, follow=False).status_code == 404)
    check("review text is HTML-escaped on display",
          b"<script>" not in page(student, f"/books/{gid}").data)
    post(c2, f"/books/{gid}/review", {"rating": "5", "review_text": "<script>alert(1)</script>"})
    check("script tag in a review is escaped", b"&lt;script&gt;" in page(student, f"/books/{gid}").data)

    # ------------------------------------------------------------ connection failure
    print("\n-- Database connection failure")
    down = create_app({"TESTING": True, "PROPAGATE_EXCEPTIONS": False, "DB_PORT": 1})
    dc = down.test_client()
    dc.get("/login")
    r = post(dc, "/login", {"email": ARJUN, "password": "Student@123"}, follow=False)
    check("unreachable database gives a clear 503 page", r.status_code == 503 and b"Database unavailable" in r.data)

    passed = sum(1 for ok, _ in results if ok)
    print(f"\n{passed} of {len(results)} checks passed.")
    DB.close()
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
