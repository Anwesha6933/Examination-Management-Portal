from flask import flash, redirect, url_for
from flask_login import current_user

from backend.helpers import home_for


def role_required(role):
    """Returns a function you attach to a blueprint with before_request."""

    def check():
        if not current_user.is_authenticated:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))

        if current_user.role != role:
            flash("You do not have access to that page.", "danger")
            return redirect(home_for(current_user))

        if role == "examiner" and current_user.examiner.status != "Approved":
            return redirect(url_for("auth.pending"))

        return None  # allowed: Flask carries on to the route

    return check