-- reset.sql : removes every object created by schema.sql and views.sql.
-- Used by "python setup_db.py --reset". Destroys all data in these tables.

DROP VIEW  IF EXISTS v_outstanding_fines;
DROP VIEW  IF EXISTS v_overdue_books;
DROP VIEW  IF EXISTS v_student_issue_history;
DROP VIEW  IF EXISTS v_librarian_issue_report;
DROP VIEW  IF EXISTS v_book_review_summary;
DROP VIEW  IF EXISTS v_book_availability;

DROP TABLE IF EXISTS BOOK_REVIEWS;
DROP TABLE IF EXISTS FINES;
DROP TABLE IF EXISTS BOOK_ISSUES;
DROP TABLE IF EXISTS BOOKS;
DROP TABLE IF EXISTS MEMBERS;
DROP TABLE IF EXISTS ROLES;
