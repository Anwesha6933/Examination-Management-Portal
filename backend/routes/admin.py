from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from backend.decorators import role_required
from backend.helpers import (EXAM_TYPES, RUBRIC_EDITABLE, STAGES, clean, course_problem,
                             exam_bookings, exam_problem, read_exam_form, read_float,
                             read_int, recount_seats, result_stats, rubric_problem,
                             signup_problem, slot_problem, stage_problem)
from backend.models import (Booking, Course, Exam, ExamSlot, Examiner, Rubric,
                            Student, User, db)
from sqlalchemy import or_

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_bp.before_request(role_required("admin"))

EXAM_FIELDS = ["title", "exam_type", "duration_minutes", "max_marks",
               "slot_creation_start", "slot_creation_end", "booking_start", "booking_end"]


# ================= Dashboard =================
@admin_bp.route("/")
def dashboard():
    tiles = [
        ("Courses", Course.query.count(), "indigo"),
        ("Examinations", Exam.query.count(), "green"),
        ("Examiners", Examiner.query.count(), "amber"),
        ("Students", Student.query.count(), "rose"),
        ("Slots", ExamSlot.query.count(), "indigo"),
        ("Active bookings", Booking.query.filter_by(status="Booked").count(), "green"),
    ]
    pending = Examiner.query.filter_by(status="Pending").count()

    counts = []
    for e in Exam.query.order_by(Exam.id).all():
        n = (Booking.query.join(ExamSlot)
             .filter(ExamSlot.exam_id == e.id, Booking.status == "Booked").count())
        counts.append((e, n))
    top = max((n for _, n in counts), default=0)
    bars = [{"title": e.title, "count": n, "pct": round(n * 100 / top) if top else 0}
            for e, n in counts]
    return render_template("admin/dashboard.html", tiles=tiles, pending=pending, bars=bars)


# ================= Courses =================
@admin_bp.route("/courses")
def courses():
    rows = Course.query.order_by(Course.code).all()
    return render_template("admin/courses.html", courses=rows)


@admin_bp.route("/courses/new", methods=["GET", "POST"])
def course_new():
    form = {"status": "Active"}
    if request.method == "POST":
        form = request.form
        code = clean(form.get("code")).upper()
        name = clean(form.get("name"))
        status = form.get("status", "")
        problem = course_problem(code, name, status)
        if problem:
            flash(problem, "danger")
        else:
            db.session.add(Course(code=code, name=name, status=status,
                                  description=clean(form.get("description")) or None))
            db.session.commit()
            flash("Course created.", "success")
            return redirect(url_for("admin.courses"))
    return render_template("admin/course_form.html", form=form, course=None)


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
def course_edit(course_id):
    course = db.get_or_404(Course, course_id)
    form = {"code": course.code, "name": course.name,
            "description": course.description or "", "status": course.status}
    if request.method == "POST":
        form = request.form
        code = clean(form.get("code")).upper()
        name = clean(form.get("name"))
        status = form.get("status", "")
        problem = course_problem(code, name, status, course.id)
        if problem:
            flash(problem, "danger")
        else:
            course.code, course.name, course.status = code, name, status
            course.description = clean(form.get("description")) or None
            db.session.commit()
            flash("Course updated.", "success")
            return redirect(url_for("admin.courses"))
    return render_template("admin/course_form.html", form=form, course=course)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
def course_delete(course_id):
    course = db.get_or_404(Course, course_id)
    if course.exams:
        flash("This course has examinations, so it cannot be deleted. Mark it Inactive instead.", "warning")
    else:
        db.session.delete(course)
        db.session.commit()
        flash("Course deleted.", "success")
    return redirect(url_for("admin.courses"))


# ================= Examinations =================
def _course_choices(exam):
    choices = Course.query.filter_by(status="Active").order_by(Course.code).all()
    if exam is not None and exam.course not in choices:
        choices.append(exam.course)
    return choices


@admin_bp.route("/exams")
def exams():
    rows = Exam.query.order_by(Exam.id.desc()).all()
    return render_template("admin/exams.html", exams=rows)


@admin_bp.route("/exams/new", methods=["GET", "POST"])
def exam_new():
    form = {}
    if request.method == "POST":
        form = request.form
        v = read_exam_form(form)
        problem = exam_problem(v)
        if problem:
            flash(problem, "danger")
        else:
            exam = Exam(course_id=v["course"].id, status="Draft")
            for key in EXAM_FIELDS:
                setattr(exam, key, v[key])
            db.session.add(exam)
            db.session.commit()
            flash("Examination created. Add its rubric and examiners next.", "success")
            return redirect(url_for("admin.exam_detail", exam_id=exam.id))
    return render_template("admin/exam_form.html", form=form, exam=None,
                           courses=_course_choices(None), exam_types=EXAM_TYPES)


@admin_bp.route("/exams/<int:exam_id>/edit", methods=["GET", "POST"])
def exam_edit(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam.status in ("Closed", "Completed"):
        flash("Closed or completed examinations cannot be edited.", "warning")
        return redirect(url_for("admin.exam_detail", exam_id=exam.id))

    form = {"course_id": exam.course_id}
    form.update({key: getattr(exam, key) for key in EXAM_FIELDS})
    if request.method == "POST":
        form = request.form
        v = read_exam_form(form)
        problem = exam_problem(v)
        rubric_total = sum(r.max_marks for r in exam.rubric)
        if not problem and v["max_marks"] < rubric_total:
            problem = f"Rubric marks already total {rubric_total:g}. Maximum marks cannot go below that."
        if problem:
            flash(problem, "danger")
        else:
            exam.course_id = v["course"].id
            for key in EXAM_FIELDS:
                setattr(exam, key, v[key])
            db.session.commit()
            flash("Examination updated.", "success")
            return redirect(url_for("admin.exam_detail", exam_id=exam.id))
    return render_template("admin/exam_form.html", form=form, exam=exam,
                           courses=_course_choices(exam), exam_types=EXAM_TYPES)


@admin_bp.route("/exams/<int:exam_id>")
def exam_detail(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    i = STAGES.index(exam.status)
    next_stage = STAGES[i + 1] if i + 1 < len(STAGES) else None
    approved = (Examiner.query.filter_by(status="Approved").join(User)
                .order_by(User.name).all())
    return render_template(
        "admin/exam_detail.html", exam=exam, next_stage=next_stage,
        rubric_total=sum(r.max_marks for r in exam.rubric),
        approved=approved, assigned_ids={e.id for e in exam.examiners},
        rubric_editable=exam.status in RUBRIC_EDITABLE,
        stats=result_stats(exam))


@admin_bp.route("/exams/<int:exam_id>/delete", methods=["POST"])
def exam_delete(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam.status != "Draft":
        flash("Only Draft examinations can be deleted.", "warning")
        return redirect(url_for("admin.exam_detail", exam_id=exam.id))
    db.session.delete(exam)
    db.session.commit()
    flash("Examination deleted.", "success")
    return redirect(url_for("admin.exams"))


@admin_bp.route("/exams/<int:exam_id>/status", methods=["POST"])
def exam_status(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    i = STAGES.index(exam.status)
    if i + 1 >= len(STAGES):
        flash("This examination is already Completed.", "info")
    else:
        problem = stage_problem(exam)
        if problem:
            flash(problem, "danger")
        else:
            exam.status = STAGES[i + 1]
            db.session.commit()
            flash(f"Examination moved to {exam.status}.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


@admin_bp.route("/exams/<int:exam_id>/examiners", methods=["POST"])
def exam_assign(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    ids = [read_int(x, 0) for x in request.form.getlist("examiner_ids")]
    chosen = Examiner.query.filter(Examiner.id.in_(ids), Examiner.status == "Approved").all()

    busy = {s.examiner_id for s in exam.slots if s.status != "Cancelled"}
    if busy - {e.id for e in chosen}:
        flash("An examiner who already has slots in this exam cannot be removed.", "warning")
    else:
        exam.examiners = chosen
        db.session.commit()
        flash("Examiners updated.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


# ================= Rubric =================
def _rubric_page(exam, item):
    if exam.status not in RUBRIC_EDITABLE:
        flash("The rubric can only change while the exam is Draft or in Slot Creation.", "warning")
        return redirect(url_for("admin.exam_detail", exam_id=exam.id))

    form = {}
    if item is not None:
        form = {"name": item.name, "max_marks": item.max_marks, "weightage": item.weightage}
    if request.method == "POST":
        form = request.form
        name = clean(form.get("name"))
        max_marks = read_float(form.get("max_marks"))
        raw = clean(form.get("weightage"))
        weightage = 0.0 if raw == "" else read_float(raw)
        problem = rubric_problem(exam, name, max_marks, weightage, item.id if item else None)
        if problem:
            flash(problem, "danger")
        else:
            if item is None:
                item = Rubric(exam_id=exam.id)
                db.session.add(item)
            item.name, item.max_marks, item.weightage = name, max_marks, weightage
            db.session.commit()
            flash("Rubric criterion saved.", "success")
            return redirect(url_for("admin.exam_detail", exam_id=exam.id))
    return render_template("admin/rubric_form.html", exam=exam, item=item, form=form)


@admin_bp.route("/exams/<int:exam_id>/rubric/new", methods=["GET", "POST"])
def rubric_new(exam_id):
    return _rubric_page(db.get_or_404(Exam, exam_id), None)


@admin_bp.route("/rubric/<int:rubric_id>/edit", methods=["GET", "POST"])
def rubric_edit(rubric_id):
    item = db.get_or_404(Rubric, rubric_id)
    return _rubric_page(item.exam, item)


@admin_bp.route("/rubric/<int:rubric_id>/delete", methods=["POST"])
def rubric_delete(rubric_id):
    item = db.get_or_404(Rubric, rubric_id)
    exam = item.exam
    if exam.status not in RUBRIC_EDITABLE:
        flash("The rubric can only change while the exam is Draft or in Slot Creation.", "warning")
    else:
        db.session.delete(item)
        db.session.commit()
        flash("Criterion removed.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))


# ================= Examiners =================
@admin_bp.route("/examiners")
def examiners():
    status = request.args.get("status", "")
    query = Examiner.query.join(User)
    if status:
        query = query.filter(Examiner.status == status)
    rows = query.order_by(User.name).all()
    return render_template("admin/examiners.html", examiners=rows, status=status,
                           statuses=["Pending", "Approved", "Rejected", "Deactivated"])


@admin_bp.route("/examiners/new", methods=["GET", "POST"])
def examiner_new():
    form = {}
    if request.method == "POST":
        form = request.form
        name = clean(form.get("name"))
        email = clean(form.get("email")).lower()
        password = form.get("password", "")
        phone = clean(form.get("phone"))
        department = clean(form.get("department"))
        problem = signup_problem("examiner", name, email, password, password, "", department)
        if problem:
            flash(problem, "danger")
        else:
            user = User(name=name, email=email, role="examiner",
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.flush()
            db.session.add(Examiner(user_id=user.id, department=department,
                                    phone=phone or None, status="Approved"))
            db.session.commit()
            flash("Examiner added and approved.", "success")
            return redirect(url_for("admin.examiners"))
    return render_template("admin/examiner_form.html", form=form)


@admin_bp.route("/examiners/<int:examiner_id>")
def examiner_detail(examiner_id):
    ex = db.get_or_404(Examiner, examiner_id)
    return render_template("admin/examiner_detail.html", ex=ex)


EXAMINER_ACTIONS = {
    "approve": ("Approved", ("Pending", "Rejected", "Deactivated")),
    "reject": ("Rejected", ("Pending",)),
    "deactivate": ("Deactivated", ("Approved",)),
}


@admin_bp.route("/examiners/<int:examiner_id>/<action>", methods=["POST"])
def examiner_status(examiner_id, action):
    ex = db.get_or_404(Examiner, examiner_id)
    if action not in EXAMINER_ACTIONS:
        flash("Unknown action.", "danger")
    else:
        new_status, allowed_from = EXAMINER_ACTIONS[action]
        if ex.status not in allowed_from:
            flash(f"A {ex.status} examiner cannot be {new_status.lower()}.", "warning")
        else:
            ex.status = new_status
            db.session.commit()
            flash(f"{ex.user.name} is now {new_status}.", "success")
    return redirect(url_for("admin.examiner_detail", examiner_id=ex.id))

# ================= Slots (M6) =================
def _active(slot):
    return [b for b in slot.bookings if b.status == "Booked"]


@admin_bp.route("/slots")
def slots():
    exam_id = read_int(request.args.get("exam_id"))
    status = request.args.get("status", "")
    query = ExamSlot.query
    if exam_id:
        query = query.filter(ExamSlot.exam_id == exam_id)
    if status in ("Available", "Full", "Cancelled"):
        query = query.filter(ExamSlot.status == status)
    rows = query.order_by(ExamSlot.slot_date.desc(), ExamSlot.start_time).all()
    return render_template("admin/slots.html", slots=rows, exam_id=exam_id, status=status,
                           exams=Exam.query.order_by(Exam.title).all())


@admin_bp.route("/slots/<int:slot_id>/examiner", methods=["POST"])
def slot_examiner(slot_id):
    slot = db.get_or_404(ExamSlot, slot_id)
    examiner = db.session.get(Examiner, read_int(request.form.get("examiner_id"), 0))

    if slot.status == "Cancelled":
        flash("A cancelled slot cannot be changed.", "warning")
    elif examiner is None or examiner.status != "Approved" or examiner not in slot.exam.examiners:
        flash("Choose an approved examiner who is assigned to this examination.", "danger")
    elif examiner.id == slot.examiner_id:
        flash("That examiner already owns this slot.", "info")
    elif any(b.evaluation for b in slot.bookings):
        flash("This slot already has evaluations, so its examiner cannot change.", "warning")
    else:
        v = {"slot_date": slot.slot_date, "start_time": slot.start_time,
             "end_time": slot.end_time, "capacity": slot.capacity}
        problem = slot_problem(slot.exam, examiner, v, slot.id)   # reuses the overlap check
        if problem:
            flash(problem, "danger")
        else:
            slot.examiner_id = examiner.id
            db.session.commit()
            flash(f"Slot now belongs to {examiner.user.name}.", "success")
    return redirect(url_for("admin.slots"))


@admin_bp.route("/slots/<int:slot_id>/cancel", methods=["POST"])
def slot_cancel(slot_id):
    slot = db.get_or_404(ExamSlot, slot_id)
    if slot.status == "Cancelled":
        flash("This slot is already cancelled.", "info")
    elif _active(slot):
        flash("This slot has active bookings. Reschedule those students first, then cancel it.", "warning")
    else:
        slot.status = "Cancelled"
        slot.available_seats = 0
        db.session.commit()
        flash("Slot cancelled.", "success")
    return redirect(url_for("admin.slots"))


# ================= Bookings (M6) =================
def _reschedule_block(booking):
    """Returns a message if this booking cannot be moved, else None."""
    if booking.status != "Booked":
        return "Only active bookings can be rescheduled."
    if booking.slot.exam.status not in ("Booking Open", "Closed"):
        return "Bookings can only be rescheduled while the exam is Booking Open or Closed."
    if booking.evaluation:
        return "This booking has already been evaluated."
    return None


@admin_bp.route("/bookings")
def bookings():
    exam_id = read_int(request.args.get("exam_id"))
    status = request.args.get("status", "")
    query = Booking.query.join(ExamSlot)
    if exam_id:
        query = query.filter(ExamSlot.exam_id == exam_id)
    if status in ("Booked", "Cancelled"):
        query = query.filter(Booking.status == status)
    rows = query.order_by(Booking.created_at.desc(), Booking.id.desc()).all()
    return render_template("admin/bookings.html", bookings=rows, exam_id=exam_id, status=status,
                           exams=Exam.query.order_by(Exam.title).all(),
                           movable={b.id for b in rows if _reschedule_block(b) is None})


@admin_bp.route("/bookings/<int:booking_id>/reschedule", methods=["GET", "POST"])
def reschedule(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    block = _reschedule_block(booking)
    if block:
        flash(block, "warning")
        return redirect(url_for("admin.bookings"))

    exam = booking.slot.exam
    targets = (ExamSlot.query
               .filter(ExamSlot.exam_id == exam.id, ExamSlot.status == "Available",
                       ExamSlot.id != booking.slot_id)
               .order_by(ExamSlot.slot_date, ExamSlot.start_time).all())

    if request.method == "POST":
        new = db.session.get(ExamSlot, read_int(request.form.get("slot_id"), 0))
        if new is None or new.exam_id != exam.id:
            flash("Choose a slot of the same examination.", "danger")
        elif new.id == booking.slot_id:
            flash("The student is already in that slot.", "info")
        elif new.status == "Cancelled":
            flash("That slot has been cancelled.", "danger")
        elif new.available_seats <= 0 or new.status == "Full":
            flash("That slot is full.", "danger")
        else:
            old = booking.slot
            booking.slot = new
            db.session.flush()
            recount_seats(old)      # old slot gets its seat back
            recount_seats(new)      # new slot loses one
            db.session.commit()
            flash("Booking rescheduled.", "success")
            return redirect(url_for("admin.bookings"))
    return render_template("admin/reschedule.html", booking=booking, exam=exam, targets=targets)
# ================= Publish results (M7) =================
@admin_bp.route("/exams/<int:exam_id>/publish", methods=["POST"])
def publish_results(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    stats = result_stats(exam)

    if exam.status not in ("Closed", "Completed"):
        flash("Results can be published only after the examination is Closed.", "warning")
    elif stats["booked"] == 0:
        flash("There are no active bookings to publish.", "warning")
    elif stats["evaluated"] < stats["booked"]:
        left = stats["booked"] - stats["evaluated"]
        flash(f"{left} student{'s' if left != 1 else ''} still to be evaluated.", "danger")
    elif stats["published"] == stats["booked"]:
        flash("Results are already published.", "info")
    else:
        for b in exam_bookings(exam):
            b.evaluation.is_published = True
        db.session.commit()
        flash("Results published. Students can see their marks now.", "success")
    return redirect(url_for("admin.exam_detail", exam_id=exam.id))

# ================= Students and history (M8) =================
@admin_bp.route("/students")
def students():
    q = clean(request.args.get("q"))
    exam_id = read_int(request.args.get("exam_id"))
    status = request.args.get("status", "")
    if status not in ("Booked", "Cancelled", "None"):
        status = ""

    query = Student.query.join(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like),
                                 Student.roll_number.ilike(like)))

    rows = []
    for s in query.order_by(User.name).all():
        items = [b for b in s.bookings if not exam_id or b.slot.exam_id == exam_id]
        booked = [b for b in items if b.status == "Booked"]
        cancelled = [b for b in items if b.status == "Cancelled"]
        if status == "Booked" and not booked:
            continue
        if status == "Cancelled" and not cancelled:
            continue
        if status == "None" and booked:
            continue
        rows.append({"student": s, "booked": len(booked), "cancelled": len(cancelled)})

    return render_template("admin/students.html", rows=rows, q=q, exam_id=exam_id,
                           status=status, exams=Exam.query.order_by(Exam.title).all())


@admin_bp.route("/students/<int:student_id>")
def student_detail(student_id):
    student = db.get_or_404(Student, student_id)
    history = sorted(student.bookings, key=lambda b: (b.created_at, b.id), reverse=True)
    return render_template("admin/student_detail.html", student=student, history=history)


# ================= Search (M8) =================
@admin_bp.route("/search")
def search():
    q = clean(request.args.get("q"))
    found = {"students": [], "examiners": [], "exams": [], "bookings": []}

    if q:
        like = f"%{q}%"
        num = read_int(q)

        cond = [User.name.ilike(like), User.email.ilike(like), Student.roll_number.ilike(like)]
        if num is not None:
            cond.append(Student.id == num)
        found["students"] = (Student.query.join(User).filter(or_(*cond))
                             .order_by(User.name).limit(50).all())

        cond = [User.name.ilike(like), User.email.ilike(like), Examiner.department.ilike(like)]
        if num is not None:
            cond.append(Examiner.id == num)
        found["examiners"] = (Examiner.query.join(User).filter(or_(*cond))
                              .order_by(User.name).limit(50).all())

        cond = [Exam.title.ilike(like), Course.code.ilike(like), Course.name.ilike(like)]
        if num is not None:
            cond.append(Exam.id == num)
        found["exams"] = (Exam.query.join(Course).filter(or_(*cond))
                          .order_by(Exam.title).limit(50).all())

        cond = [User.name.ilike(like), Student.roll_number.ilike(like), Exam.title.ilike(like)]
        if num is not None:
            cond.append(Booking.id == num)
        found["bookings"] = (
            Booking.query
            .join(Student, Booking.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .join(ExamSlot, Booking.slot_id == ExamSlot.id)
            .join(Exam, ExamSlot.exam_id == Exam.id)
            .filter(or_(*cond))
            .order_by(Booking.id.desc()).limit(50).all())

    total = sum(len(v) for v in found.values())
    return render_template("admin/search.html", q=q, found=found, total=total)