from flask import Flask

from backend.config import Config
from backend.models import db
from backend.seed import seed_admin

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()
    seed_admin()


@app.route("/")
def home():
    return "Examly is running"


if __name__ == "__main__":
    app.run(debug=True)