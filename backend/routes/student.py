import csv
import io
from datetime import date

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from sqlalchemy import or_

from backend.decorators import role_required
from backend.helpers import (EXAM_TYPES, active_booking, booking_problem, can_book,
                             can_cancel, clean, read_int, recount_seats)
from backend.models import Booking, Course, Evaluation, Exam, ExamSlot, db

student_bp = Blueprint("student", __name__, url_prefix="/student")
student_bp.before_request(role_required("student"))

VISIBLE = ("Booking Open", "Closed", "Completed")


def me():
    return current_user.student


def _my_active_bookings():
    return Booking.query.filter_by(student_id=me().id, status="Booked")


def _visible_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam.status not in VISIBLE:
        abort(404)
    return exam


# ================= Dashboard =================
@student_bp.route("/")
def dashboard():
    today = date.today()
    open_exams = [e for e in Exam.query.filter_by(status="Booking Open").all() if can_book(e, today)]
    open_slots = sum(1 for e in open_exams for s in e.slots if s.status == "Available")

    mine = _my_active_bookings().all()
    upcoming = sorted((b for b in mine if b.slot.slot_date >= today),
                      key=lambda b: (b.slot.slot_date, b.slot.start_time))
    published = (Evaluation.query.join(Booking)
                 .filter(Booking.student_id == me().id, Evaluation.is_published.is_(True))
                 .count())

    tiles = [
        ("Available exams", len(open_exams), "indigo"),
        ("Available slots", open_slots, "green"),
        ("Upcoming exams", len(upcoming), "amber"),
        ("Booked slots", len(mine), "rose"),
        ("Published results", published, "indigo"),
    ]
    return render_template("student/dashboard.html", tiles=tiles, upcoming=upcoming)


# ================= Profile =================
@student_bp.route("/profile", methods=["GET", "POST"])
def profile():
    form = {"name": current_user.name, "phone": me().phone or ""}
    if request.method == "POST":
        form = request.form
        name = clean(form.get("name"))
        phone = clean(form.get("phone"))
        if not name:
            flash("Name is required.", "danger")
        else:
            current_user.name = name
            me().phone = phone or None
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("student.profile"))
    return render_template("student/profile.html", form=form)


# ================= Exams: search, filter, detail =================
@student_bp.route("/exams")
def exams():
    f = {
        "q": clean(request.args.get("q")),
        "course_id": read_int(request.args.get("course_id")),
        "exam_type": clean(request.args.get("exam_type")),
        "status": clean(request.args.get("status")),
    }
    query = Exam.query.join(Course).filter(Exam.status.in_(VISIBLE))
    if f["q"]:
        like = f"%{f['q']}%"
        query = query.filter(or_(Exam.title.ilike(like), Course.code.ilike(like),
                                 Course.name.ilike(like)))
    if f["course_id"]:
        query = query.filter(Exam.course_id == f["course_id"])
    if f["exam_type"] in EXAM_TYPES:
        query = query.filter(Exam.exam_type == f["exam_type"])
    if f["status"] in VISIBLE:
        query = query.filter(Exam.status == f["status"])

    rows = query.order_by(Exam.booking_start.desc()).all()
    return render_template("student/exams.html", exams=rows, f=f,
                           courses=Course.query.order_by(Course.code).all(),
                           exam_types=EXAM_TYPES, statuses=VISIBLE)


@student_bp.route("/exams/<int:exam_id>")
def exam_detail(exam_id):
    exam = _visible_exam(exam_id)
    slots = (ExamSlot.query.filter(ExamSlot.exam_id == exam.id, ExamSlot.status != "Cancelled")
             .order_by(ExamSlot.slot_date, ExamSlot.start_time).all())
    return render_template("student/exam_detail.html", exam=exam, slots=slots,
                           mine=active_booking(me(), exam), open_now=can_book(exam))


# ================= Booking =================
@student_bp.route("/slots/<int:slot_id>/book", methods=["GET", "POST"])
def book(slot_id):
    slot = db.get_or_404(ExamSlot, slot_id)
    if slot.exam.status not in VISIBLE:
        abort(404)

    problem = booking_problem(me(), slot)       # checked on GET and POST
    if problem:
        flash(problem, "danger")
        return redirect(url_for("student.exam_detail", exam_id=slot.exam_id))

    if request.method == "POST":
        db.session.add(Booking(student_id=me().id, slot_id=slot.id, status="Booked"))
        db.session.flush()
        recount_seats(slot)
        db.session.commit()
        flash("Your slot is booked.", "success")
        return redirect(url_for("student.bookings"))
    return render_template("student/confirm.html", slot=slot, exam=slot.exam)


@student_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
def cancel(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.student_id != me().id:           # own bookings only
        abort(404)

    if booking.status != "Booked":
        flash("This booking is already cancelled.", "info")
    elif not can_cancel(booking):
        flash(f"Bookings can only be cancelled up to {booking.slot.exam.booking_end}, "
              f"while booking is open.", "warning")
    else:
        booking.status = "Cancelled"
        db.session.flush()
        recount_seats(booking.slot)
        db.session.commit()
        flash("Booking cancelled.", "success")
    return redirect(url_for("student.bookings"))


@student_bp.route("/bookings")
def bookings():
    rows = (Booking.query.filter_by(student_id=me().id)
            .order_by(Booking.created_at.desc(), Booking.id.desc()).all())
    return render_template("student/bookings.html", bookings=rows,
                           cancellable={b.id for b in rows if can_cancel(b)})
# ================= Results (M7) =================
def _published():
    return (Evaluation.query.join(Booking)
            .filter(Booking.student_id == me().id, Evaluation.is_published.is_(True))
            .order_by(Evaluation.evaluated_at.desc()).all())


def _csv_safe(value):
    """Stops a spreadsheet from running text that starts like a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@student_bp.route("/results")
def results():
    return render_template("student/results.html", evaluations=_published())


@student_bp.route("/results/<int:evaluation_id>")
def result_detail(evaluation_id):
    ev = db.get_or_404(Evaluation, evaluation_id)
    if ev.booking.student_id != me().id or not ev.is_published:   # own and published only
        abort(404)
    return render_template("student/result_detail.html", ev=ev,
                           slot=ev.booking.slot, exam=ev.booking.slot.exam)


@student_bp.route("/results/scorecard.csv")
def scorecard():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Roll number", "Name", "Examination", "Course", "Date", "Examiner",
                     "Criterion", "Marks", "Max marks", "Remarks"])
    for ev in _published():
        slot = ev.booking.slot
        exam = slot.exam
        base = [me().roll_number, current_user.name, _csv_safe(exam.title), exam.course.code,
                slot.slot_date, _csv_safe(slot.examiner.user.name)]
        for s in ev.scores:
            writer.writerow(base + [_csv_safe(s.rubric.name), f"{s.marks:g}",
                                    f"{s.rubric.max_marks:g}", _csv_safe(s.remarks)])
        writer.writerow(base + ["TOTAL", f"{ev.total_marks:g}", exam.max_marks,
                                _csv_safe(ev.remarks)])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=scorecard.csv"})