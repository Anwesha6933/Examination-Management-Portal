from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from backend.decorators import role_required
from backend.helpers import (can_create_slots, can_edit_slots, clean,
                             read_slot_form, slot_problem)
from backend.models import Booking, Exam, ExamSlot, db

examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner")
examiner_bp.before_request(role_required("examiner"))


def me():
    return current_user.examiner


def _visible_exams():
    """Exams assigned to this examiner. Draft exams stay hidden."""
    return [e for e in me().exams if e.status != "Draft"]


def _my_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam not in _visible_exams():
        abort(404)
    return exam


def _my_slot(slot_id):
    slot = db.get_or_404(ExamSlot, slot_id)
    if slot.examiner_id != me().id:     # own slots only
        abort(404)
    return slot


def _my_bookings():
    return (Booking.query.join(ExamSlot)
            .filter(ExamSlot.examiner_id == me().id, Booking.status == "Booked"))


# ================= Dashboard =================
@examiner_bp.route("/")
def dashboard():
    slots_created = ExamSlot.query.filter(
        ExamSlot.examiner_id == me().id, ExamSlot.status != "Cancelled").count()
    pending = _my_bookings().filter(~Booking.evaluation.has()).count()
    tiles = [
        ("Assigned exams", len(_visible_exams()), "indigo"),
        ("Slots created", slots_created, "green"),
        ("Students booked", _my_bookings().count(), "amber"),
        ("Evaluations pending", pending, "rose"),
    ]
    open_exams = [e for e in _visible_exams() if can_create_slots(e)]
    return render_template("examiner/dashboard.html", tiles=tiles, open_exams=open_exams)


# ================= Profile =================
@examiner_bp.route("/profile", methods=["GET", "POST"])
def profile():
    form = {"name": current_user.name, "phone": me().phone or "",
            "department": me().department}
    if request.method == "POST":
        form = request.form
        name = clean(form.get("name"))
        phone = clean(form.get("phone"))
        department = clean(form.get("department"))
        if not name:
            flash("Name is required.", "danger")
        elif not department:
            flash("Department is required.", "danger")
        else:
            current_user.name = name
            me().phone = phone or None
            me().department = department
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("examiner.profile"))
    return render_template("examiner/profile.html", form=form)


# ================= Exams =================
@examiner_bp.route("/exams")
def exams():
    rows = sorted(_visible_exams(), key=lambda e: e.id, reverse=True)
    counts = {e.id: ExamSlot.query.filter(
                  ExamSlot.exam_id == e.id, ExamSlot.examiner_id == me().id,
                  ExamSlot.status != "Cancelled").count() for e in rows}
    return render_template("examiner/exams.html", exams=rows, counts=counts)


@examiner_bp.route("/exams/<int:exam_id>")
def exam_detail(exam_id):
    exam = _my_exam(exam_id)
    slots = (ExamSlot.query.filter_by(exam_id=exam.id, examiner_id=me().id)
             .order_by(ExamSlot.slot_date, ExamSlot.start_time).all())
    return render_template("examiner/exam_detail.html", exam=exam, slots=slots,
                           can_create=can_create_slots(exam),
                           can_edit=can_edit_slots(exam))


# ================= Slots =================
@examiner_bp.route("/exams/<int:exam_id>/slots/new", methods=["GET", "POST"])
def slot_new(exam_id):
    exam = _my_exam(exam_id)
    if not can_create_slots(exam):          # checked on GET and POST
        flash(f"Slots can only be created while the exam is in Slot Creation, "
              f"between {exam.slot_creation_start} and {exam.slot_creation_end}.", "warning")
        return redirect(url_for("examiner.exam_detail", exam_id=exam.id))

    form = {"capacity": 1}
    if request.method == "POST":
        form = request.form
        v = read_slot_form(form)
        problem = slot_problem(exam, me(), v)
        if problem:
            flash(problem, "danger")
        else:
            db.session.add(ExamSlot(
                exam_id=exam.id, examiner_id=me().id,
                slot_date=v["slot_date"], start_time=v["start_time"],
                end_time=v["end_time"], capacity=v["capacity"],
                available_seats=v["capacity"], status="Available"))
            db.session.commit()
            flash("Slot created.", "success")
            return redirect(url_for("examiner.exam_detail", exam_id=exam.id))
    return render_template("examiner/slot_form.html", exam=exam, slot=None, form=form)


def _slot_locked(slot):
    """Returns a message if this slot may not be edited or removed, else None."""
    if slot.status == "Cancelled":
        return "This slot is cancelled."
    if not can_edit_slots(slot.exam):
        return "Slots can only be edited or removed before booking opens."
    if slot.bookings:
        return "This slot already has bookings."
    return None


@examiner_bp.route("/slots/<int:slot_id>/edit", methods=["GET", "POST"])
def slot_edit(slot_id):
    slot = _my_slot(slot_id)
    locked = _slot_locked(slot)
    if locked:
        flash(locked, "warning")
        return redirect(url_for("examiner.exam_detail", exam_id=slot.exam_id))

    form = {"slot_date": slot.slot_date,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "capacity": slot.capacity}
    if request.method == "POST":
        form = request.form
        v = read_slot_form(form)
        problem = slot_problem(slot.exam, me(), v, slot.id)
        if problem:
            flash(problem, "danger")
        else:
            slot.slot_date, slot.start_time = v["slot_date"], v["start_time"]
            slot.end_time, slot.capacity = v["end_time"], v["capacity"]
            slot.available_seats = v["capacity"]      # no bookings yet
            db.session.commit()
            flash("Slot updated.", "success")
            return redirect(url_for("examiner.exam_detail", exam_id=slot.exam_id))
    return render_template("examiner/slot_form.html", exam=slot.exam, slot=slot, form=form)


@examiner_bp.route("/slots/<int:slot_id>/delete", methods=["POST"])
def slot_delete(slot_id):
    slot = _my_slot(slot_id)
    exam_id = slot.exam_id
    locked = _slot_locked(slot)
    if locked:
        flash(locked, "warning")
    else:
        db.session.delete(slot)
        db.session.commit()
        flash("Slot removed.", "success")
    return redirect(url_for("examiner.exam_detail", exam_id=exam_id))