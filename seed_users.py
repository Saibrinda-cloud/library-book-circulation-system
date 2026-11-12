"""Create the demo accounts with properly hashed passwords.

Run after schema.sql and before seed.sql:   python seed_users.py
Re-running resets these demo accounts' passwords to the values below.
These credentials are for local demonstration only.
"""
import psycopg

from config import Config
from security import hash_password

LIBRARIAN_PASSWORD = "Librarian@123"
STUDENT_PASSWORD = "Student@123"

# (role, full name, e-mail, phone)
DEMO_MEMBERS = [
    ("Librarian", "Meera Nair",        "meera.nair@college.example",     "9000000001"),
    ("Student",   "Arjun Kumar",       "arjun.kumar@college.example",    "9000000002"),
    ("Student",   "Divya Menon",       "divya.menon@college.example",    "9000000003"),
    ("Student",   "Karthik Rao",       "karthik.rao@college.example",    None),
    ("Student",   "Sneha Iyer",        "sneha.iyer@college.example",     "9000000005"),
    ("Student",   "Rahul Sharma",      "rahul.sharma@college.example",   "9000000006"),
    ("Student",   "Priya Nair",        "priya.nair@college.example",     "9000000007"),
    ("Student",   "Faizan Ahmed",      "faizan.ahmed@college.example",   None),
    ("Student",   "Lakshmi Narayanan", "lakshmi.n@college.example",      "9000000009"),
    ("Student",   "Anitha Raj",        "anitha.raj@college.example",     "9000000010"),
]


def seed_members(conn):
    with conn.transaction():
        for role, name, email, phone in DEMO_MEMBERS:
            password = LIBRARIAN_PASSWORD if role == "Librarian" else STUDENT_PASSWORD
            conn.execute(
                "INSERT INTO MEMBERS (role_id, full_name, email, password_hash, phone) "
                "SELECT role_id, %s, %s, %s, %s FROM ROLES WHERE role_name = %s "
                "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash",
                (name, email, hash_password(password), phone, role),
            )
    return len(DEMO_MEMBERS)


def connect():
    return psycopg.connect(
        host=Config.DB_HOST, port=Config.DB_PORT, dbname=Config.DB_NAME,
        user=Config.DB_USER, password=Config.DB_PASSWORD, connect_timeout=5, autocommit=True,
    )


if __name__ == "__main__":
    with connect() as connection:
        count = seed_members(connection)
    print(f"{count} demo members created or updated in database '{Config.DB_NAME}'.")
    print(f"  Librarian: meera.nair@college.example / {LIBRARIAN_PASSWORD}")
    print(f"  Students : arjun.kumar@college.example (and others) / {STUDENT_PASSWORD}")
