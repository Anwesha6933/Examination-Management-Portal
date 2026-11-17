from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from backend.decorators import role_required
from backend.helpers import (EXAM_TYPES, RUBRIC_EDITABLE, STAGES, clean, course_problem,
                             exam_problem, read_exam_form, read_float, read_int,
                             rubric_problem, signup_problem, stage_problem)
from backend.models import (Booking, Course, Exam, ExamSlot, Examiner, Rubric,
                            Student, User, db)

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
    return render_template("admin/dashboard.html", tiles=tiles, pending=pending)


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
        rubric_editable=exam.status in RUBRIC_EDITABLE)


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