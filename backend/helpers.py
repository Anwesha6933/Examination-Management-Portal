import re
from datetime import datetime

from flask import url_for

from backend.models import User, Student

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLL_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")



def clean(value):
    return (value or "").strip()


def read_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def read_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None



def signup_problem(role, name, email, password, confirm, roll_number="", department=""):
    if role not in ("student", "examiner"):
        return "Please choose Student or Examiner."
    if not name:
        return "Name is required."
    if not EMAIL_RE.match(email):
        return "Enter a valid email address."
    if User.query.filter_by(email=email).first():
        return "That email is already registered."
    if len(password) < 6:
        return "Password must be at least 6 characters."
    if password != confirm:
        return "Passwords do not match."
    if role == "student":
        if not ROLL_RE.match(roll_number):
            return "Enter a valid roll number (6 to 20 letters or digits)."
        if Student.query.filter_by(roll_number=roll_number.upper()).first():
            return "That roll number is already registered."
    else:
        if not department:
            return "Department is required for examiners."
    return None



def home_for(user):
    """URL of the dashboard that belongs to this user's role."""
    endpoint = {
        "admin": "admin.dashboard",
        "examiner": "examiner.dashboard",
        "student": "student.dashboard",
    }[user.role]
    return url_for(endpoint)


BADGE_COLORS = {
    "Active": "success", "Approved": "success", "Available": "success",
    "Booking Open": "success", "Booked": "primary", "Pending": "warning",
    "Draft": "secondary", "Slot Creation": "info", "Full": "danger",
    "Cancelled": "danger", "Rejected": "danger", "Deactivated": "danger",
    "Closed": "dark", "Completed": "secondary", "Inactive": "secondary",
}


def status_color(status):
    return BADGE_COLORS.get(status, "secondary")