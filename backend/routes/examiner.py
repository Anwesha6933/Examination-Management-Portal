from flask import Blueprint, render_template

from backend.decorators import role_required

examiner_bp = Blueprint("examiner", __name__, url_prefix="/examiner")
examiner_bp.before_request(role_required("examiner"))


@examiner_bp.route("/")
def dashboard():
    return render_template("examiner/dashboard.html")