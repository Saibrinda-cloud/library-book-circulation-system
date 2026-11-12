"""Small helpers shared by several routes."""
import math
import re

from flask import request


def like_pattern(text):
    """Turn user text into a safe ILIKE pattern: %, _ and \\ in the text are matched literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def to_int(raw):
    """Parse a non-negative whole number from a form field; return None if invalid."""
    raw = (raw or "").strip()
    return int(raw) if re.fullmatch(r"[0-9]{1,9}", raw) else None


def get_page():
    return max(1, to_int(request.args.get("page")) or 1)


class Pagination:
    def __init__(self, page, per_page, total):
        self.per_page = per_page
        self.total = total
        self.pages = max(1, math.ceil(total / per_page))
        self.page = min(page, self.pages)

    @property
    def offset(self):
        return (self.page - 1) * self.per_page

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages
