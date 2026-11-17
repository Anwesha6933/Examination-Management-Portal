import re
from datetime import datetime

from flask import url_for

from backend.models import Course, Student, User, db

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


EXAM_TYPES = ["Viva", "Practical", "Oral", "Project Demo"]
STAGES = ["Draft", "Slot Creation", "Booking Open", "Closed", "Completed"]
RUBRIC_EDITABLE = ("Draft", "Slot Creation")


def course_problem(code, name, status, course_id=None):
    if not code:
        return "Course code is required."
    if not name:
        return "Course name is required."
    if status not in ("Active", "Inactive"):
        return "Choose Active or Inactive."
    other = Course.query.filter_by(code=code).first()
    if other and other.id != course_id:
        return "That course code already exists."
    return None


def read_exam_form(form):
    return {
        "course": db.session.get(Course, read_int(form.get("course_id"), 0)),
        "title": clean(form.get("title")),
        "exam_type": clean(form.get("exam_type")),
        "duration_minutes": read_int(form.get("duration_minutes")),
        "max_marks": read_int(form.get("max_marks")),
        "slot_creation_start": read_date(form.get("slot_creation_start")),
        "slot_creation_end": read_date(form.get("slot_creation_end")),
        "booking_start": read_date(form.get("booking_start")),
        "booking_end": read_date(form.get("booking_end")),
    }


def exam_problem(v):
    if v["course"] is None:
        return "Choose a course."
    if not v["title"]:
        return "Title is required."
    if v["exam_type"] not in EXAM_TYPES:
        return "Choose an exam type."
    if v["duration_minutes"] is None or v["duration_minutes"] <= 0:
        return "Duration must be a positive number of minutes."
    if v["max_marks"] is None or v["max_marks"] <= 0:
        return "Maximum marks must be a positive number."
    dates = [v["slot_creation_start"], v["slot_creation_end"], v["booking_start"], v["booking_end"]]
    if None in dates:
        return "All four dates are required."
    if v["slot_creation_start"] > v["slot_creation_end"]:
        return "Slot creation cannot end before it starts."
    if v["booking_start"] > v["booking_end"]:
        return "Booking cannot end before it starts."
    if v["booking_start"] < v["slot_creation_start"]:
        return "Booking cannot start before slot creation starts."
    return None


def rubric_problem(exam, name, max_marks, weightage, rubric_id=None):
    if not name:
        return "Criterion name is required."
    if max_marks is None or max_marks <= 0:
        return "Marks must be a positive number."
    if weightage is None or not 0 <= weightage <= 100:
        return "Weightage must be between 0 and 100."
    used = sum(r.max_marks for r in exam.rubric if r.id != rubric_id)
    if used + max_marks > exam.max_marks:
        return f"Rubric marks would reach {used + max_marks:g}, above the exam maximum of {exam.max_marks}."
    return None


def stage_problem(exam):
    """Checks before the admin moves an exam forward. Later milestones add more."""
    if exam.status == "Draft":
        if not exam.rubric:
            return "Add rubric criteria before opening slot creation."
        total = sum(r.max_marks for r in exam.rubric)
        if abs(total - exam.max_marks) > 0.001:
            return f"Rubric marks add up to {total:g}, but the exam maximum is {exam.max_marks}."
        if not exam.examiners:
            return "Assign at least one examiner first."
    return None