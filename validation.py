"""Server-side validation of form input. Each validator returns (clean_data, errors)."""
import re
from decimal import Decimal

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ISBN_RE = re.compile(r"^[0-9][0-9-]{8,18}[0-9Xx]$")
PHONE_RE = re.compile(r"^[0-9+][0-9 -]{6,18}$")
MONEY_RE = re.compile(r"^[0-9]{1,6}(\.[0-9]{1,2})?$")


def _text(form, name, label, errors, max_len, required=False):
    value = (form.get(name) or "").strip()
    if not value:
        if required:
            errors[name] = f"{label} is required."
        return None
    if len(value) > max_len:
        errors[name] = f"{label} must be at most {max_len} characters."
        return None
    return value


def _int(form, name, label, errors, minimum, maximum, required=True):
    raw = (form.get(name) or "").strip()
    if raw == "":
        if required:
            errors[name] = f"{label} is required."
        return None
    if not re.fullmatch(r"-?[0-9]{1,9}", raw):
        errors[name] = f"{label} must be a whole number."
        return None
    number = int(raw)
    if number < minimum or number > maximum:
        errors[name] = f"{label} must be between {minimum} and {maximum}."
        return None
    return number


def validate_book(form):
    errors = {}
    data = {
        "title": _text(form, "title", "Title", errors, 200, required=True),
        "author": _text(form, "author", "Author", errors, 250, required=True),
        "category": _text(form, "category", "Category", errors, 60, required=True),
        "publisher": _text(form, "publisher", "Publisher", errors, 100),
        "publication_year": _int(form, "publication_year", "Publication year", errors,
                                 1000, 2100, required=False),
        "total_copies": _int(form, "total_copies", "Total copies", errors, 0, 100000),
        "damaged_copies": _int(form, "damaged_copies", "Damaged copies", errors, 0, 100000),
    }
    isbn = _text(form, "isbn", "ISBN", errors, 20)
    if isbn is not None and not ISBN_RE.match(isbn):
        errors["isbn"] = "ISBN must be 10 to 20 characters: digits and hyphens (last character may be X)."
        isbn = None
    data["isbn"] = isbn
    if (data["total_copies"] is not None and data["damaged_copies"] is not None
            and data["damaged_copies"] > data["total_copies"]):
        errors["damaged_copies"] = "Damaged copies cannot exceed total copies."
    return data, errors


def validate_member(form, valid_role_ids, is_new):
    errors = {}
    data = {"full_name": _text(form, "full_name", "Full name", errors, 100, required=True)}

    email = _text(form, "email", "E-mail", errors, 150, required=True)
    if email is not None:
        email = email.lower()
        if not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid e-mail address."
            email = None
    data["email"] = email

    phone = _text(form, "phone", "Phone", errors, 20)
    if phone is not None and not PHONE_RE.match(phone):
        errors["phone"] = "Phone may contain digits, spaces, hyphens and a leading +."
        phone = None
    data["phone"] = phone

    role_raw = (form.get("role_id") or "").strip()
    if role_raw.isdigit() and int(role_raw) in valid_role_ids:
        data["role_id"] = int(role_raw)
    else:
        data["role_id"] = None
        errors["role_id"] = "Choose a role."

    password = form.get("password") or ""
    if is_new or password:
        if len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        elif len(password) > 128:
            errors["password"] = "Password must be at most 128 characters."
    data["password"] = password or None
    return data, errors


def validate_review(form):
    errors = {}
    rating = _int(form, "rating", "Rating", errors, 1, 5)
    text = _text(form, "review_text", "Review", errors, 1000)
    return {"rating": rating, "review_text": text}, errors


def parse_money(raw):
    """Parse a rupee amount with at most two decimals (> 0); return None if invalid."""
    raw = (raw or "").strip()
    if not MONEY_RE.match(raw):
        return None
    value = Decimal(raw)
    return value if value > 0 else None
