from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    username = "admin"
    password = "admin123"
    full_name = "Administrator"

    existing = User.query.filter_by(username=username).first()
    if existing:
        print("Admin already exists.")
    else:
        admin = User(
            username=username,
            password_hash=User.hash_password(password),
            role="admin",
            full_name=full_name
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully!")
