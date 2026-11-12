-- schema.sql : Library Management System (PostgreSQL 12 or later)
-- Run order: schema.sql -> views.sql -> seed_users.py -> seed.sql
-- Six core tables, created in dependency-safe order.

CREATE TABLE ROLES (
    role_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name  VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE MEMBERS (
    member_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_id        INTEGER NOT NULL,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    phone          VARCHAR(20),
    joined_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_members_role FOREIGN KEY (role_id)
        REFERENCES ROLES (role_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_members_email CHECK (POSITION('@' IN email) > 1)
);

CREATE TABLE BOOKS (
    book_id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn              VARCHAR(20) UNIQUE,            -- nullable: UNIQUE ignores NULLs
    title             VARCHAR(200) NOT NULL,
    author            VARCHAR(250) NOT NULL,
    category          VARCHAR(60)  NOT NULL,
    publisher         VARCHAR(100),
    publication_year  INTEGER,
    total_copies      INTEGER NOT NULL DEFAULT 1,    -- all physical copies, including damaged
    damaged_copies    INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_books_isbn    CHECK (isbn IS NULL OR LENGTH(isbn) >= 10),
    CONSTRAINT chk_books_year    CHECK (publication_year IS NULL
                                        OR publication_year BETWEEN 1000 AND 2100),
    CONSTRAINT chk_books_total   CHECK (total_copies >= 0),
    CONSTRAINT chk_books_damaged CHECK (damaged_copies >= 0
                                        AND damaged_copies <= total_copies)
);

CREATE TABLE BOOK_ISSUES (
    issue_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id    INTEGER NOT NULL,
    book_id      INTEGER NOT NULL,
    issue_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date     DATE NOT NULL,
    return_date  DATE,                               -- NULL until the book is returned
    CONSTRAINT fk_issues_member FOREIGN KEY (member_id)
        REFERENCES MEMBERS (member_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_issues_book FOREIGN KEY (book_id)
        REFERENCES BOOKS (book_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_issues_due    CHECK (due_date >= issue_date),
    CONSTRAINT chk_issues_return CHECK (return_date IS NULL OR return_date >= issue_date)
);

CREATE TABLE FINES (
    issue_id     INTEGER PRIMARY KEY,                -- shared primary key and foreign key
    amount       NUMERIC(8,2) NOT NULL,
    amount_paid  NUMERIC(8,2) NOT NULL DEFAULT 0,
    status       VARCHAR(10)  NOT NULL DEFAULT 'Unpaid',
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fines_issue FOREIGN KEY (issue_id)
        REFERENCES BOOK_ISSUES (issue_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_fines_amount CHECK (amount > 0),
    CONSTRAINT chk_fines_paid   CHECK (amount_paid >= 0 AND amount_paid <= amount),
    CONSTRAINT chk_fines_status CHECK (
           (status = 'Unpaid'  AND amount_paid = 0)
        OR (status = 'Partial' AND amount_paid > 0 AND amount_paid < amount)
        OR (status = 'Paid'    AND amount_paid = amount))
);

CREATE TABLE BOOK_REVIEWS (
    review_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id    INTEGER NOT NULL,
    book_id      INTEGER NOT NULL,
    rating       INTEGER NOT NULL,
    review_text  TEXT,
    review_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT fk_reviews_member FOREIGN KEY (member_id)
        REFERENCES MEMBERS (member_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_reviews_book FOREIGN KEY (book_id)
        REFERENCES BOOKS (book_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT uq_review_member_book UNIQUE (member_id, book_id)
);

-- ------------------------------------------------------------------
-- Indexes (justified by the application's queries)
-- ------------------------------------------------------------------
CREATE INDEX idx_issues_member ON BOOK_ISSUES (member_id);
CREATE INDEX idx_reviews_book  ON BOOK_REVIEWS (book_id);
-- Availability counts only look at unreturned issues of one book.
CREATE INDEX idx_issues_book_open ON BOOK_ISSUES (book_id) WHERE return_date IS NULL;
-- A student cannot hold two unreturned copies of the same book at once.
CREATE UNIQUE INDEX uq_issues_open_member_book
    ON BOOK_ISSUES (member_id, book_id) WHERE return_date IS NULL;

-- ------------------------------------------------------------------
-- Reference data: the application depends on these two role names.
-- ------------------------------------------------------------------
INSERT INTO ROLES (role_name) VALUES ('Librarian'), ('Student');
