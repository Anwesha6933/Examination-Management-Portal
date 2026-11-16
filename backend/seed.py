from werkzeug.security import generate_password_hash
from backend.models import db, User


def seed_admin():
    if User.query.filter_by(role="admin").first() is None:
        admin = User(
            name="Administrator",
            email="admin@emp.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()