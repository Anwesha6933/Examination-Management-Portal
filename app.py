from flask import Flask, render_template
from flask_login import LoginManager

from backend.config import Config
from backend.helpers import status_color
from backend.models import User, db
from backend.routes.admin import admin_bp
from backend.routes.auth import auth_bp
from backend.routes.examiner import examiner_bp
from backend.routes.student import student_bp
from backend.seed import seed_admin
from backend.routes.api import api_bp


app = Flask(__name__, template_folder="frontend/templates", static_folder="frontend/static")
app.config.from_object(Config)

db.init_app(app)
app.register_blueprint(api_bp)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.jinja_env.filters["badge"] = status_color

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(examiner_bp)
app.register_blueprint(student_bp)


@app.errorhandler(404)
def not_found(error):
    return render_template("_empty.html"), 404


with app.app_context():
    db.create_all()
    seed_admin()


if __name__ == "__main__":
    app.run(debug=True)