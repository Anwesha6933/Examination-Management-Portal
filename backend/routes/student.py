from flask import Blueprint, render_template

from backend.decorators import role_required

student_bp = Blueprint("student", __name__, url_prefix="/student")
student_bp.before_request(role_required("student"))


@student_bp.route("/")
def dashboard():
    return render_template("student/dashboard.html")