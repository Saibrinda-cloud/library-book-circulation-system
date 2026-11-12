# Library Management System (Flask, Psycopg 3 and PostgreSQL)

A small database-driven web application for a college library. A **librarian** manages books and members, issues and returns books and records fine payments. A **student** searches the catalogue, sees only their own borrowing history, due dates and fines, and reviews books.

| Layer | Technology | Role |
|---|---|---|
| Interface | HTML and CSS (Jinja templates) | Pages and forms |
| Application | Python **Flask** | Handles requests, sessions, roles, validation |
| Database driver | **Psycopg 3** | Python's connection to PostgreSQL (sends SQL, returns rows) |
| Database | **PostgreSQL** | Stores data, enforces constraints, runs queries and views |

Flow: `Browser (HTML/CSS)` to `Flask` to `Psycopg` to `PostgreSQL`, and back.

Library rules used everywhere: loan period **14 days**; fine **Rs. 2 per overdue day**, created when an overdue book is returned; outstanding fine = amount - amount_paid.

---

## 1. What is in the project folder

```
library_management_system/
├── app.py               Flask application (run this)
├── config.py            reads settings from .env
├── db.py                Psycopg 3 database connection
├── security.py          password hashing, CSRF, login and role checks
├── services.py          issue / return / fine-payment transactions
├── validation.py        form validation
├── utils.py             search and pagination helpers
├── setup_db.py          builds the database (tables, views, accounts, sample data)
├── seed_users.py        creates the demo accounts with hashed passwords
├── smoke_test.py        automated test (uses ONLY the library_test database)
├── requirements.txt     Python packages
├── .env.example         template for your private .env file
├── .gitignore
├── README.md            this file
├── sql/
│   ├── create_database.sql   creates the PostgreSQL user and databases
│   ├── schema.sql            6 tables, constraints, indexes, the two roles
│   ├── views.sql             6 reporting views
│   ├── seed.sql              sample books, issues, fines, reviews
│   └── reset.sql             drops all project tables and views
├── routes/              auth, dashboard, books, reviews, members, circulation, fines, reports
├── templates/           HTML pages
└── static/css/style.css
```

The ZIP does **not** contain a `.env` file. You create it in Step 6.

---

## 2. Required software

| Software | Version | Notes |
|---|---|---|
| Python | 3.10 or newer (tested with 3.12) | Windows installer: tick **"Add python.exe to PATH"** |
| PostgreSQL | 14 or newer (tested with 16) | Install the server, **pgAdmin** and the command-line tools. Remember the password you set for the `postgres` user |
| Visual Studio Code | any recent version | Install the **Python** extension (Microsoft) |

Check the installs in a terminal:

```
python --version
psql --version
```

If `python` is not recognised on Windows, try `py --version` and use `py` instead of `python` below. If `psql` is not recognised, see Troubleshooting (problem 1).

---

## 3. Step-by-step: from opening VS Code to logging in

Commands are for **Windows PowerShell** inside VS Code's terminal. macOS/Linux differences are in the notes.

### Step 1: Unzip and open the project in VS Code

1. Unzip `library_management_system.zip`.
2. Open VS Code, choose **File > Open Folder...** and select the folder that **directly contains `app.py`** (the inner `library_management_system` folder). Click **Yes, I trust the authors** if asked.
3. The Explorer panel on the left must show `app.py`, `sql`, `templates` and so on at the top level. If you only see one folder inside it, you opened the wrong level. Open the inner folder instead.
4. Open a terminal: **Terminal > New Terminal** (or press Ctrl + `). The prompt should end with the project folder name. Check with:
   ```
   dir app.py
   ```
   (macOS/Linux: `ls app.py`). It must show the file.

### Step 2: Create and activate a virtual environment

A virtual environment keeps this project's Python packages separate from the rest of your computer.

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

When it works, the prompt starts with `(.venv)`.

- **Command Prompt (cmd)** instead of PowerShell: `.venv\Scripts\activate.bat`
- **PowerShell says "running scripts is disabled"**: run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, then activate again. This only affects the current terminal window.
- **macOS/Linux**: `python3 -m venv .venv` then `source .venv/bin/activate`
- Tell VS Code to use it: press Ctrl+Shift+P, choose **Python: Select Interpreter**, and pick the entry containing `.venv`.

You must activate the environment again every time you open a new terminal.

### Step 3: Install the Python packages

With `(.venv)` showing:

```
pip install -r requirements.txt
```

This installs Flask, Psycopg 3 (`psycopg[binary]`) and python-dotenv. Verify:

```
python -c "import flask, psycopg, dotenv; print('packages OK')"
```

### Step 4: Create the PostgreSQL user and databases

This is done **once**, as the PostgreSQL superuser (`postgres`). The script `sql/create_database.sql` contains exactly these three statements:

```sql
CREATE USER lms_user WITH PASSWORD 'lms_password_change_me';
CREATE DATABASE library_db OWNER lms_user;
CREATE DATABASE library_test OWNER lms_user;
```

- `library_db` is the real application database.
- `library_test` is a separate, disposable database used only by `smoke_test.py`.

**Option A: command line.** In the VS Code terminal:

```
psql -U postgres -h localhost -f sql/create_database.sql
```

Enter the `postgres` password when asked. You should see `CREATE ROLE`, `CREATE DATABASE` and `CREATE DATABASE`.

**Option B: pgAdmin.** Open pgAdmin, connect to the server, right-click the `postgres` database, choose **Query Tool**, paste one statement at a time from `sql/create_database.sql`, and run each one separately (F5). Run them separately because PostgreSQL does not allow `CREATE DATABASE` inside a multi-statement batch.

**Want a different password?** Edit the password in `sql/create_database.sql` **before** running it, and use the same password in `.env` (Step 5). Otherwise keep the default `lms_password_change_me`, which is fine for local use.

Check it worked:

```
psql -U lms_user -h localhost -d library_db -c "SELECT current_user;"
```

It should print `lms_user`.

### Step 5: Create your `.env` file

`.env` holds your private settings. It is listed in `.gitignore` and must never be shared.

1. Copy the template:
   ```
   copy .env.example .env
   ```
   (macOS/Linux: `cp .env.example .env`)
2. Generate a secret key:
   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Open `.env` in VS Code and edit it. It must look like this, with **your** key and **your** password:
   ```
   SECRET_KEY=<paste the long random text here>
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=library_db
   DB_USER=lms_user
   DB_PASSWORD=lms_password_change_me
   LOAN_PERIOD_DAYS=14
   FINE_PER_DAY=2.00
   ```
4. Rules: no quotes, no spaces around `=`, and save the file. `DB_PASSWORD` must match the password used in Step 4. Change `DB_PORT` only if PostgreSQL was installed on a different port.

The application **refuses to start** while `SECRET_KEY` is empty or still begins with `replace-with`.

### Step 6: Build the database

Run this one command (the database must still be empty):

```
python setup_db.py
```

It runs the scripts in this exact order:

1. `sql/schema.sql` (6 tables, constraints, indexes, and the `Librarian` and `Student` roles)
2. `sql/views.sql` (6 views)
3. `seed_users.py` logic (the 10 demo members, with properly hashed passwords)
4. `sql/seed.sql` (20 books, 21 issues, 5 fines, 11 reviews)

Expected output:

```
Setting up database 'library_db' on localhost:5432 ...
  ran schema.sql
  ran views.sql
  created demo members (seed_users)
  ran seed.sql
Done.
```

Other forms of the command:

| Command | What it does |
|---|---|
| `python setup_db.py --reset` | **Deletes all data in the six tables and views**, then rebuilds everything. Use it to start over |
| `python setup_db.py --schema-only` | Tables and views only, with no accounts and no sample data |
| `python seed_users.py` | Only (re)creates the demo accounts and resets their passwords |

**Manual alternative** (only if you prefer running each script yourself). The order matters, because the sample data needs the members to exist first:

```
psql -U lms_user -h localhost -d library_db -f sql/schema.sql
psql -U lms_user -h localhost -d library_db -f sql/views.sql
python seed_users.py
psql -U lms_user -h localhost -d library_db -f sql/seed.sql
```

Optional check, which should print `20`:

```
psql -U lms_user -h localhost -d library_db -c "SELECT COUNT(*) FROM books;"
```

### Step 7: Start the application

```
flask --app app run
```

You should see a line like `Running on http://127.0.0.1:5000`. Leave this terminal running. (`python app.py` also works. For automatic reload while editing code, use `flask --app app run --debug`.)

If `flask` is not recognised, the virtual environment is not active. Run `python -m flask --app app run` instead.

To stop the server, press **Ctrl + C** in that terminal.

### Step 8: Open the website and log in

Open **http://127.0.0.1:5000** in your browser. (`http://localhost:5000` also works.) You will see the login page.

Log in with a demo account:

| Role | E-mail | Password |
|---|---|---|
| **Librarian** | `meera.nair@college.example` | `Librarian@123` |
| **Student** | `arjun.kumar@college.example` | `Student@123` |

After logging in:

- the librarian lands on **Circulation desk** (statistics, most overdue books, menu: Books, Issue and return, Fines, Members, Reports);
- the student lands on **Welcome, Arjun** (books on loan, overdue count, fine balance; menu: Books, My borrowing, Popular books).

**You are successfully set up when:** the login works, the librarian sees the Circulation desk with numbers on it, and the student sees only their own loans.

---

## 4. Demo accounts

All accounts are created by `seed_users.py` and are for **local demonstration only**. Delete or change them before any real use.

| Role | E-mail | Password | Notes |
|---|---|---|---|
| Librarian | `meera.nair@college.example` | `Librarian@123` | Full access |
| Student | `arjun.kumar@college.example` | `Student@123` | Has an open loan |
| Student | `divya.menon@college.example` | `Student@123` | |
| Student | `karthik.rao@college.example` | `Student@123` | Has an overdue book |
| Student | `sneha.iyer@college.example` | `Student@123` | Has an overdue book |
| Student | `rahul.sharma@college.example` | `Student@123` | Has an overdue book |
| Student | `priya.nair@college.example` | `Student@123` | |
| Student | `faizan.ahmed@college.example` | `Student@123` | Holds the only copy of "Clean Code" |
| Student | `lakshmi.n@college.example` | `Student@123` | Has an overdue book |
| Student | `anitha.raj@college.example` | `Student@123` | Never borrowed |

The sample dates are relative to today's date, so there are always some overdue books.

---

## 5. Running the automated smoke test safely

`smoke_test.py` checks logins, roles, books, issue and return, fines, payments, reviews, rollback and more. It uses Flask's test client, so you do not need the server running.

**Safety rules built into the script:**

- It runs **only** against a database whose name ends in `_test`. By default that is `library_test`.
- If you pass any other name (for example `--db library_db`), it stops immediately with `Refusing to run: the database name must end with '_test'`.
- On every run it **drops and rebuilds all six tables in `library_test`**. Your real `library_db` is never touched.

**Before the first run**, `library_test` must exist. It is created by `sql/create_database.sql` (Step 4). If you created your databases by hand and skipped it, create it as the postgres user:

```
psql -U postgres -h localhost -c "CREATE DATABASE library_test OWNER lms_user;"
```

**Run it** (virtual environment active, from the project folder):

```
python smoke_test.py
```

The first lines must say `Rebuilding scratch database 'library_test' ...`. Each check prints `PASS` or `FAIL`. At the end you should see:

```
122 of 122 checks passed.
```

(That is the result from my own test run on PostgreSQL 16. If your count or result differs, send me the output.)

Two kinds of error text in the middle of the output are **expected**, because the test deliberately causes them: a logged `Return failed for issue ...` traceback (a forced numeric overflow, used to prove the transaction rolls back) and a `Database connection failed` message (a deliberately wrong port, used to test the 503 page). Only lines starting with `FAIL` indicate a problem.

---

## 6. Common errors and solutions

**1. `psql` is not recognised.**
PostgreSQL's `bin` folder is not on your PATH. Either run it with the full path, for example
`& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -f sql/create_database.sql` (replace `16` with your version), or open **SQL Shell (psql)** from the Start menu, or use pgAdmin (Step 4, Option B).

**2. `password authentication failed for user "lms_user"` (or "Cannot connect to PostgreSQL ... authentication failed").**
`DB_PASSWORD` in `.env` does not match the password set in `create_database.sql`. Either fix `.env`, or reset the password as the superuser:
`psql -U postgres -h localhost -c "ALTER USER lms_user WITH PASSWORD 'lms_password_change_me';"`

**3. `role "lms_user" already exists` / `database "library_db" already exists`.**
`create_database.sql` was already run. This is harmless. Do not run it again; continue with Step 5.

**4. `Connection refused` / "Cannot connect to PostgreSQL".**
The server is not running, or the port is wrong. On Windows open **Services** (Win + R, then `services.msc`), find `postgresql-x64-<version>` and start it. Check that `DB_PORT` in `.env` matches the port chosen during installation (default 5432).

**5. `database "library_db" does not exist`.**
Step 4 was not completed, or `DB_NAME` in `.env` is misspelled. Run Step 4.

**6. `RuntimeError: SECRET_KEY is not set`.**
`.env` is missing, is not in the folder that contains `app.py`, or `SECRET_KEY` is still `replace-with-a-long-random-value`. Do Step 5. If you edit `.env` while the server is running, stop it (Ctrl + C) and start it again.

**7. `Tables already exist. Run again with --reset ...`**
The database was already built. Keep it, or wipe and rebuild with `python setup_db.py --reset` (this deletes the data).

**8. `relation "roles" does not exist` (or "books", "members"...).**
The tables were not created in this database. Run `python setup_db.py` and check that `DB_NAME` is `library_db`.

**9. `ModuleNotFoundError: No module named 'flask'` (or `psycopg`, `dotenv`).**
The virtual environment is not active, or the packages are not installed. Activate it (Step 2; the prompt must show `(.venv)`), run `pip install -r requirements.txt`, and make sure VS Code uses the `.venv` interpreter.

**10. `pip` cannot install `psycopg-binary`.**
Your Python version is probably too new or too old for a ready-made package. Use Python 3.10 to 3.12 (3.12 was used for testing), then recreate `.venv`.

**11. "Incorrect e-mail or password" for a demo account.**
Check the exact e-mail (it ends in `@college.example`) and the password (capital letters matter). If you skipped part of Step 6, or the database was built with `--schema-only`, run `python seed_users.py` to create the accounts and reset their passwords, then run `python setup_db.py --reset` if the sample books are also missing.

**12. Browser shows "400 Request not accepted: The form expired or is invalid".**
The page was open for a long time, or cookies are blocked, or you restarted the server. Reload the page and try again.

**13. Browser shows "503 Database unavailable".**
The app is running but cannot reach PostgreSQL. Start the PostgreSQL service and check the `DB_*` values in `.env`.

**14. `Address already in use` / port 5000 is busy.**
Another program uses port 5000. Use another port: `flask --app app run --port 5001`, then open `http://127.0.0.1:5001`.

**15. `flask` is not recognised.**
The virtual environment is not active. Activate it, or use `python -m flask --app app run`.

**16. PowerShell: "running scripts is disabled on this system".**
Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, then activate again. Or use Command Prompt with `.venv\Scripts\activate.bat`.

**17. `smoke_test.py`: "Refusing to run: the database name must end with '_test'".**
That is the safety guard. Use `python smoke_test.py` (default `library_test`) or a name such as `--db my_scratch_test`.

**18. `smoke_test.py`: `database "library_test" does not exist`.**
Create it with the command in section 5.

**19. The overdue list is empty after many days.**
Overdue books are measured against today's date. Re-run `python setup_db.py --reset` to regenerate sample data relative to today's date.

**20. Pages look unstyled.**
Hard-refresh the browser (Ctrl + F5). Check that `static/css/style.css` exists and that the server terminal shows no errors.

---

## 7. Security notes

- Passwords are stored only as salted PBKDF2-SHA256 hashes. All SQL uses parameterised queries. Every form carries a CSRF token.
- Roles are checked on the server for every request, and a student's `member_id` always comes from the server-side session, never from a URL or form field.
- Keep `.env` private. Remove the demo accounts and use HTTPS (set `SESSION_COOKIE_SECURE = True` in `config.py`) before any real deployment.
- The built-in Flask server (`flask run`) is for local development and demonstration only.
