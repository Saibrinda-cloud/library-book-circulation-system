"""Business operations that must succeed or fail as a unit (each runs in one transaction).

Inventory model: individual physical copies are not stored. Availability is calculated:
    available = total_copies - damaged_copies - (unreturned issues of the book)
Every function locks the relevant row with SELECT ... FOR UPDATE, so two librarians
cannot issue the last available copy at the same moment.
"""


class RuleViolation(Exception):
    """A business rule was broken; the message is safe to show to the user."""


def issue_book(conn, member_id, book_id, loan_days):
    with conn.transaction():
        book = conn.execute(
            "SELECT book_id, title, total_copies, damaged_copies "
            "FROM BOOKS WHERE book_id = %s FOR UPDATE",
            (book_id,),
        ).fetchone()
        if book is None:
            raise RuleViolation("That book does not exist.")

        member = conn.execute(
            "SELECT m.member_id, m.full_name FROM MEMBERS m "
            "INNER JOIN ROLES r ON r.role_id = m.role_id "
            "WHERE m.member_id = %s AND r.role_name = 'Student'",
            (member_id,),
        ).fetchone()
        if member is None:
            raise RuleViolation("Choose a registered student.")

        on_loan = conn.execute(
            "SELECT COUNT(*) AS n FROM BOOK_ISSUES WHERE book_id = %s AND return_date IS NULL",
            (book_id,),
        ).fetchone()["n"]
        if book["total_copies"] - book["damaged_copies"] - on_loan <= 0:
            raise RuleViolation(f"No copy of \u201c{book['title']}\u201d is available right now.")

        issue = conn.execute(
            "INSERT INTO BOOK_ISSUES (member_id, book_id, issue_date, due_date) "
            "VALUES (%s, %s, CURRENT_DATE, CURRENT_DATE + %s::integer) "
            "RETURNING issue_id, issue_date, due_date",
            (member_id, book_id, loan_days),
        ).fetchone()
    return book, member, issue


def return_book(conn, issue_id, fine_per_day):
    """Close an issue and, if it is late, create the fine in the same transaction."""
    with conn.transaction():
        issue = conn.execute(
            "SELECT i.issue_id, i.return_date, b.title, m.full_name "
            "FROM BOOK_ISSUES i "
            "INNER JOIN BOOKS b ON b.book_id = i.book_id "
            "INNER JOIN MEMBERS m ON m.member_id = i.member_id "
            "WHERE i.issue_id = %s FOR UPDATE OF i",
            (issue_id,),
        ).fetchone()
        if issue is None:
            raise RuleViolation("Issue record not found.")
        if issue["return_date"] is not None:
            raise RuleViolation("This book has already been returned.")

        closed = conn.execute(
            "UPDATE BOOK_ISSUES SET return_date = CURRENT_DATE "
            "WHERE issue_id = %s AND return_date IS NULL "
            "RETURNING return_date - due_date AS days_late",
            (issue_id,),
        ).fetchone()

        fine = None
        if closed["days_late"] > 0:
            # Same rule everywhere: fine = overdue days x fine rate.
            fine = conn.execute(
                "INSERT INTO FINES (issue_id, amount) "
                "SELECT issue_id, (return_date - due_date) * %s::numeric "
                "FROM BOOK_ISSUES WHERE issue_id = %s AND return_date > due_date "
                "RETURNING amount, status",
                (fine_per_day, issue_id),
            ).fetchone()
    return issue, closed["days_late"], fine


def record_payment(conn, issue_id, payment):
    with conn.transaction():
        fine = conn.execute(
            "SELECT amount, amount_paid FROM FINES WHERE issue_id = %s FOR UPDATE",
            (issue_id,),
        ).fetchone()
        if fine is None:
            raise RuleViolation("No fine exists for that issue.")
        balance = fine["amount"] - fine["amount_paid"]
        if balance <= 0:
            raise RuleViolation("This fine is already paid in full.")
        if payment > balance:
            raise RuleViolation(f"The payment is more than the outstanding balance (Rs. {balance:,.2f}).")
        return conn.execute(
            "UPDATE FINES SET amount_paid = amount_paid + %s, "
            "status = CASE WHEN amount_paid + %s >= amount THEN 'Paid' ELSE 'Partial' END "
            "WHERE issue_id = %s RETURNING amount, amount_paid, status",
            (payment, payment, issue_id),
        ).fetchone()
