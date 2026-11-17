from flask import Blueprint, jsonify, request
from flask_login import current_user

from backend.models import Booking, Exam, Examiner, ExamSlot, Student, db

api_bp = Blueprint("api", __name__, url_prefix="/api")

STUDENT_VISIBLE = ("Booking Open", "Closed", "Completed")


@api_bp.before_request
def need_login():
    if not current_user.is_authenticated:
        return jsonify(error="Login required."), 401
    if current_user.role == "examiner" and current_user.examiner.status != "Approved":
        return jsonify(error="Your account is not approved."), 403
    return None


def admin_only():
    if current_user.role != "admin":
        return jsonify(error="Admin only."), 403
    return None


def iso(value):
    return value.isoformat() if value else None


def hhmm(value):
    return value.strftime("%H:%M") if value else None


# ---------- who can see what ----------
def exam_visible(exam):
    role = current_user.role
    if role == "admin":
        return True
    if role == "examiner":
        return exam.status != "Draft" and exam in current_user.examiner.exams
    return exam.status in STUDENT_VISIBLE


def visible_slots(exam):
    role = current_user.role
    if role == "admin":
        slots = list(exam.slots)
    elif role == "examiner":
        slots = [s for s in exam.slots if s.examiner_id == current_user.examiner.id]
    else:
        slots = [s for s in exam.slots if s.status != "Cancelled"]
    return sorted(slots, key=lambda s: (s.slot_date, s.start_time))


# ---------- turning rows into JSON ----------
def exam_json(exam, full=False):
    data = {
        "id": exam.id,
        "title": exam.title,
        "course": {"id": exam.course.id, "code": exam.course.code, "name": exam.course.name},
        "type": exam.exam_type,
        "duration_minutes": exam.duration_minutes,
        "max_marks": exam.max_marks,
        "status": exam.status,
        "slot_creation": {"start": iso(exam.slot_creation_start), "end": iso(exam.slot_creation_end)},
        "booking": {"start": iso(exam.booking_start), "end": iso(exam.booking_end)},
    }
    if full:
        data["rubric"] = [{"id": r.id, "name": r.name, "max_marks": r.max_marks,
                           "weightage": r.weightage} for r in exam.rubric]
        data["examiners"] = [{"id": e.id, "name": e.user.name, "department": e.department}
                             for e in exam.examiners]
        data["slots"] = [{"id": s.id, "date": iso(s.slot_date), "start_time": hhmm(s.start_time),
                          "end_time": hhmm(s.end_time), "examiner": s.examiner.user.name,
                          "capacity": s.capacity, "available_seats": s.available_seats,
                          "status": s.status} for s in visible_slots(exam)]
    return data


def booking_json(b):
    s = b.slot
    return {
        "id": b.id,
        "status": b.status,
        "booked_on": iso(b.created_at),
        "student": {"id": b.student.id, "name": b.student.user.name,
                    "roll_number": b.student.roll_number},
        "exam": {"id": s.exam_id, "title": s.exam.title},
        "slot": {"id": s.id, "date": iso(s.slot_date), "start_time": hhmm(s.start_time),
                 "end_time": hhmm(s.end_time), "examiner": s.examiner.user.name},
    }


# ---------- endpoints ----------
@api_bp.route("/exams")
def exams():
    rows = [e for e in Exam.query.order_by(Exam.id).all() if exam_visible(e)]
    status = request.args.get("status", "")
    if status:
        rows = [e for e in rows if e.status == status]
    return jsonify(count=len(rows), exams=[exam_json(e) for e in rows])


@api_bp.route("/exams/<int:exam_id>")
def exam_detail(exam_id):
    exam = db.session.get(Exam, exam_id)
    if exam is None or not exam_visible(exam):
        return jsonify(error="Examination not found."), 404
    return jsonify(exam_json(exam, full=True))


@api_bp.route("/examiners")
def examiners():
    denied = admin_only()
    if denied:
        return denied
    rows = Examiner.query.order_by(Examiner.id).all()
    return jsonify(count=len(rows), examiners=[
        {"id": e.id, "name": e.user.name, "email": e.user.email,
         "department": e.department, "phone": e.phone, "status": e.status} for e in rows])


@api_bp.route("/students")
def students():
    denied = admin_only()
    if denied:
        return denied
    rows = Student.query.order_by(Student.id).all()
    return jsonify(count=len(rows), students=[
        {"id": s.id, "name": s.user.name, "email": s.user.email,
         "roll_number": s.roll_number, "phone": s.phone} for s in rows])


@api_bp.route("/bookings")
def bookings():
    query = Booking.query.join(ExamSlot)
    if current_user.role == "student":
        query = query.filter(Booking.student_id == current_user.student.id)
    elif current_user.role == "examiner":
        query = query.filter(ExamSlot.examiner_id == current_user.examiner.id)

    status = request.args.get("status", "")
    if status in ("Booked", "Cancelled"):
        query = query.filter(Booking.status == status)
    exam_id = request.args.get("exam_id", type=int)
    if exam_id:
        query = query.filter(ExamSlot.exam_id == exam_id)

    rows = query.order_by(Booking.id).all()
    return jsonify(count=len(rows), bookings=[booking_json(b) for b in rows])