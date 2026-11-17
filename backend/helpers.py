import re
from datetime import date, datetime

from flask import url_for
from backend.models import Booking, Course, ExamSlot, Student, User, db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLL_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")

PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")


def phone_problem(phone):
    if phone and not PHONE_RE.match(phone):
        return "Enter a valid phone number (7 to 20 digits, spaces, + or -)."
    return None



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



def signup_problem(role, name, email, password, confirm, roll_number="", department="", phone=""):
    if role not in ("student", "examiner"):
        return "Please choose Student or Examiner."
    if not name:
        return "Name is required."
    if len(name) > 100:
        return "Name is too long (100 characters at most)."
    if not EMAIL_RE.match(email) or len(email) > 120:
        return "Enter a valid email address."
    if User.query.filter_by(email=email).first():
        return "That email is already registered."
    if len(password) < 6:
        return "Password must be at least 6 characters."
    if len(password) > 100:
        return "Password is too long (100 characters at most)."
    if password != confirm:
        return "Passwords do not match."
    problem = phone_problem(phone)
    if problem:
        return problem
    if role == "student":
        if not ROLL_RE.match(roll_number):
            return "Enter a valid roll number (6 to 20 letters or digits)."
        if Student.query.filter_by(roll_number=roll_number.upper()).first():
            return "That roll number is already registered."
    else:
        if not department:
            return "Department is required for examiners."
        if len(department) > 100:
            return "Department is too long (100 characters at most)."
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
    if len(code) > 20 or len(name) > 100:
        return "Course code can be 20 characters and the name 100 at most."
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
    if len(v["title"]) > 150:
        return "Title is too long (150 characters at most)."
    if v["course"] is None:
        return "Choose a course."
    if not v["title"]:
        return "Title is required."
    if v["exam_type"] not in EXAM_TYPES:
        return "Choose an exam type."
    if v["duration_minutes"] is None or not 1 <= v["duration_minutes"] <= 600:
        return "Duration must be between 1 and 600 minutes."
    if v["max_marks"] is None or not 1 <= v["max_marks"] <= 1000:
        return "Maximum marks must be between 1 and 1000."
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
    if len(name) > 100:
        return "Criterion name is too long (100 characters at most)."
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
def can_create_slots(exam, today=None):
    """Slots can be created only in Slot Creation status, inside the slot-creation dates."""
    today = today or date.today()
    return (exam.status == "Slot Creation"
            and exam.slot_creation_start <= today <= exam.slot_creation_end)


def can_edit_slots(exam, today=None):
    """Slots can be edited or removed only before booking opens."""
    today = today or date.today()
    return exam.status == "Slot Creation" and today < exam.booking_start


def read_slot_form(form):
    return {
        "slot_date": read_date(form.get("slot_date")),
        "start_time": read_time(form.get("start_time")),
        "end_time": read_time(form.get("end_time")),
        "capacity": read_int(form.get("capacity")),
    }


def slot_problem(exam, examiner, v, slot_id=None):
    """Returns a message, or None if the slot is fine."""
    if v["slot_date"] is None:
        return "Choose a valid date."
    if v["start_time"] is None or v["end_time"] is None:
        return "Enter valid start and end times."
    if v["end_time"] <= v["start_time"]:
        return "End time must be after the start time."
    if v["capacity"] is None or v["capacity"] < 1:
        return "Capacity must be at least 1."
    if v["slot_date"] < exam.booking_end:
        return f"The slot date cannot be before the booking end date ({exam.booking_end})."

    same_day = ExamSlot.query.filter(
        ExamSlot.examiner_id == examiner.id,
        ExamSlot.slot_date == v["slot_date"],
        ExamSlot.status != "Cancelled",
    ).all()
    for other in same_day:
        if other.id != slot_id and v["start_time"] < other.end_time and other.start_time < v["end_time"]:
            return "This overlaps another slot of yours on the same day."
    return None


def can_book(exam, today=None):
    """Booking works only in Booking Open status, inside the booking dates."""
    today = today or date.today()
    return (exam.status == "Booking Open"
            and exam.booking_start <= today <= exam.booking_end)


def can_cancel(booking, today=None):
    """A student may cancel until the booking end date, while booking is still open."""
    today = today or date.today()
    exam = booking.slot.exam
    return (booking.status == "Booked"
            and exam.status == "Booking Open"
            and today <= exam.booking_end)


def active_booking(student, exam):
    """The student's current (not cancelled) booking in this exam, or None."""
    return (Booking.query.join(ExamSlot)
            .filter(Booking.student_id == student.id,
                    ExamSlot.exam_id == exam.id,
                    Booking.status == "Booked")
            .first())


def recount_seats(slot):
    """Recalculate seats from the bookings and flip Available/Full. Call after every change."""
    taken = Booking.query.filter_by(slot_id=slot.id, status="Booked").count()
    slot.available_seats = max(slot.capacity - taken, 0)
    if slot.status != "Cancelled":
        slot.status = "Full" if slot.available_seats == 0 else "Available"


def booking_problem(student, slot):
    """Returns a message if this student cannot book this slot, else None."""
    exam = slot.exam
    if slot.status == "Cancelled":
        return "This slot has been cancelled."
    if not can_book(exam):
        return (f"Booking is not open for this examination "
                f"(window: {exam.booking_start} to {exam.booking_end}).")
    if active_booking(student, exam):
        return "You already have a booking for this examination. Cancel it first to choose another slot."
    if slot.available_seats <= 0 or slot.status == "Full":
        return "This slot is full."
    return None
# ---------- M7: evaluation and results ----------
def evaluation_block(booking):
    """Returns a message if this booking cannot be graded right now, else None."""
    if booking.status != "Booked":
        return "Only active bookings can be evaluated."
    if booking.slot.exam.status != "Closed":
        return "Evaluation opens when the admin moves the examination to Closed."
    if booking.evaluation and booking.evaluation.is_published:
        return "Results are published, so this evaluation is locked."
    return None


def read_scores(exam, form):
    """Reads one marks box and one remark box per rubric criterion.
    Returns (rows, None) or (None, error message)."""
    rows = []
    for r in exam.rubric:
        marks = read_float(clean(form.get(f"marks_{r.id}")))
        remark = clean(form.get(f"remark_{r.id}"))
        if marks is None:
            return None, f"Enter marks for '{r.name}'."
        if marks < 0 or marks > r.max_marks:
            return None, f"Marks for '{r.name}' must be between 0 and {r.max_marks:g}."
        if len(remark) > 255:
            return None, f"The remark for '{r.name}' is too long (255 characters at most)."
        rows.append((r, marks, remark or None))
    return rows, None


def exam_bookings(exam):
    """All active bookings of an exam."""
    return (Booking.query.join(ExamSlot)
            .filter(ExamSlot.exam_id == exam.id, Booking.status == "Booked").all())


def result_stats(exam):
    bookings = exam_bookings(exam)
    evaluated = [b for b in bookings if b.evaluation]
    published = [b for b in evaluated if b.evaluation.is_published]
    return {"booked": len(bookings), "evaluated": len(evaluated), "published": len(published)}