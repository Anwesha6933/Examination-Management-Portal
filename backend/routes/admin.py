from flask import Blueprint, render_template

from backend.decorators import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_bp.before_request(role_required("admin"))


@admin_bp.route("/")
def dashboard():
    return render_template("admin/dashboard.html")