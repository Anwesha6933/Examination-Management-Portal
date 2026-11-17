from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from backend.helpers import clean, home_for, signup_problem
from backend.models import Examiner, Student, User, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    return render_template("auth/index.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))

    email = ""
    if request.method == "POST":
        email = clean(request.form.get("email")).lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user is None or not check_password_hash(user.password_hash, password):
            flash("Wrong email or password.", "danger")
        elif user.role == "examiner" and user.examiner.status in ("Deactivated", "Rejected"):
            flash("This account is not active. Please contact the admin.", "danger")
        else:
            login_user(user)
            return redirect(home_for(user))

    return render_template("auth/login.html", email=email)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))

    if request.method == "POST":
        role = request.form.get("role", "")
        name = clean(request.form.get("name"))
        email = clean(request.form.get("email")).lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        phone = clean(request.form.get("phone"))
        roll_number = clean(request.form.get("roll_number"))
        department = clean(request.form.get("department"))

        problem = signup_problem(role, name, email, password, confirm, roll_number, department)
        if problem:
            flash(problem, "danger")
            return render_template("auth/register.html", form=request.form)

        user = User(name=name, email=email, role=role,
                    password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()  

        if role == "student":
            db.session.add(Student(user_id=user.id, roll_number=roll_number.upper(),
                                   phone=phone or None))
        else:
            db.session.add(Examiner(user_id=user.id, department=department,
                                    phone=phone or None, status="Pending"))
        db.session.commit()

        login_user(user)
        if role == "examiner":
            return redirect(url_for("auth.pending"))
        flash("Welcome to Examly!", "success")
        return redirect(home_for(user))

    return render_template("auth/register.html", form={})


@auth_bp.route("/pending")
@login_required
def pending():
    if current_user.role != "examiner":
        return redirect(home_for(current_user))

    status = current_user.examiner.status
    if status == "Approved":
        return redirect(url_for("examiner.dashboard"))
    if status != "Pending":
        logout_user()
        flash("This account is not active. Please contact the admin.", "danger")
        return redirect(url_for("auth.login"))
    return render_template("auth/pending.html")