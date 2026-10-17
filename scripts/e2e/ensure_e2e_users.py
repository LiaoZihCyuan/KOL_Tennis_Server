"""Create (or reset) dedicated E2E test accounts in the LOCAL dev database.

Only ever run inside the dev container, via harness.ensure_users():
    docker exec -e E2E_DEV_ONLY=1 flask_api_dev python3 scripts/e2e/ensure_e2e_users.py

The local DB may hold a copy of production data, so we never log in as a real
user; these e2e_* accounts are ours to create and reset freely.
"""
import os
import sys

if os.environ.get("E2E_DEV_ONLY") != "1":
    sys.exit("Refusing to run: set E2E_DEV_ONLY=1 (dev container only, never production).")

sys.path.insert(0, "/app")

from werkzeug.security import generate_password_hash  # noqa: E402

from extensions import db  # noqa: E402
from manage import app  # noqa: E402
from models.user import User, UserRole  # noqa: E402

PASSWORD = "e2e-pass-123"
ACCOUNTS = [
    ("e2e_admin", "E2E 管理員", UserRole.ADMIN, None),
    ("e2e_coach", "E2E 教練", UserRole.COACH, "#64748B"),
    ("e2e_student", "E2E 學生", UserRole.STUDENT, None),
]

with app.app_context():
    for username, display_name, role, color in ACCOUNTS:
        user = db.session.query(User).filter(User.username == username).first()
        if user is None:
            user = User(username=username, display_name=display_name, role=role, color=color)
            db.session.add(user)
        user.password_hash = generate_password_hash(PASSWORD)
        user.deleted_at = None
        user.role = role
    db.session.commit()
    print("e2e users ready:", ", ".join(a[0] for a in ACCOUNTS))
