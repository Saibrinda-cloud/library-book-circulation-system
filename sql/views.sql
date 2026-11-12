-- views.sql : reporting views used by the application.
-- Available copies = total_copies - damaged_copies - currently issued (unreturned) copies.

CREATE OR REPLACE VIEW v_book_availability AS
SELECT b.book_id, b.isbn, b.title, b.author, b.category, b.publisher,
       b.publication_year, b.total_copies, b.damaged_copies,
       COUNT(i.issue_id) AS currently_issued,
       b.total_copies - b.damaged_copies - COUNT(i.issue_id) AS available_copies
FROM BOOKS b
LEFT JOIN BOOK_ISSUES i
       ON i.book_id = b.book_id AND i.return_date IS NULL
GROUP BY b.book_id;

CREATE OR REPLACE VIEW v_book_review_summary AS
SELECT b.book_id, b.title, b.author,
       COUNT(r.review_id)      AS review_count,
       ROUND(AVG(r.rating), 2) AS average_rating
FROM BOOKS b
LEFT JOIN BOOK_REVIEWS r ON r.book_id = b.book_id
GROUP BY b.book_id;

-- Librarian view: every issue with member, book, overdue days and fine balance.
CREATE OR REPLACE VIEW v_librarian_issue_report AS
SELECT i.issue_id, i.member_id, m.full_name AS member_name, m.email AS member_email,
       i.book_id, b.title, i.issue_date, i.due_date, i.return_date,
       CASE WHEN i.return_date IS NULL AND i.due_date < CURRENT_DATE
            THEN CURRENT_DATE - i.due_date ELSE 0 END      AS days_overdue,
       COALESCE(f.amount, 0)                               AS fine_amount,
       COALESCE(f.amount_paid, 0)                          AS fine_paid,
       f.status                                            AS fine_status,
       COALESCE(f.amount - f.amount_paid, 0)               AS fine_balance
FROM BOOK_ISSUES i
INNER JOIN MEMBERS m ON m.member_id = i.member_id
INNER JOIN BOOKS   b ON b.book_id   = i.book_id
LEFT JOIN  FINES   f ON f.issue_id  = i.issue_id;

-- Student view: no other member's name, e-mail or password data is exposed.
-- The application always filters it with WHERE member_id = <id from the session>.
CREATE OR REPLACE VIEW v_student_issue_history AS
SELECT i.member_id, i.issue_id, i.book_id, b.title, b.author,
       i.issue_date, i.due_date, i.return_date,
       CASE WHEN i.return_date IS NULL AND i.due_date < CURRENT_DATE
            THEN CURRENT_DATE - i.due_date ELSE 0 END      AS days_overdue,
       COALESCE(f.amount, 0)                               AS fine_amount,
       COALESCE(f.amount_paid, 0)                          AS fine_paid,
       f.status                                            AS fine_status,
       COALESCE(f.amount - f.amount_paid, 0)               AS fine_balance
FROM BOOK_ISSUES i
INNER JOIN BOOKS b ON b.book_id  = i.book_id
LEFT JOIN  FINES f ON f.issue_id = i.issue_id;

-- Unreturned books that are past their due date.
CREATE OR REPLACE VIEW v_overdue_books AS
SELECT i.issue_id, i.member_id, m.full_name AS member_name, m.email AS member_email,
       i.book_id, b.title, i.issue_date, i.due_date,
       CURRENT_DATE - i.due_date AS days_overdue
FROM BOOK_ISSUES i
INNER JOIN MEMBERS m ON m.member_id = i.member_id
INNER JOIN BOOKS   b ON b.book_id   = i.book_id
WHERE i.return_date IS NULL AND i.due_date < CURRENT_DATE;

-- Fines that still have a balance (outstanding = amount - amount_paid).
CREATE OR REPLACE VIEW v_outstanding_fines AS
SELECT f.issue_id, i.member_id, m.full_name AS member_name, b.title,
       i.due_date, i.return_date, f.amount, f.amount_paid,
       f.amount - f.amount_paid AS balance, f.status, f.created_at
FROM FINES f
INNER JOIN BOOK_ISSUES i ON i.issue_id  = f.issue_id
INNER JOIN MEMBERS     m ON m.member_id = i.member_id
INNER JOIN BOOKS       b ON b.book_id   = i.book_id
WHERE f.amount - f.amount_paid > 0;
