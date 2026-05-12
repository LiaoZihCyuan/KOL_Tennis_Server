from typing import Optional, Dict, Any, List
from werkzeug.security import generate_password_hash
from extensions import db
from models.user import User, UserRole

class UserService:
    @staticmethod
    def get_all_users() -> list[User]:
        return db.session.query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at.desc()).all()

    @staticmethod
    def get_coaches() -> List[User]:
        return User.get_users_by_role(UserRole.COACH)

    @staticmethod
    def get_students() -> List[User]:
        return User.get_users_by_role(UserRole.STUDENT)

    @staticmethod
    def create_user(data: Dict[str, Any]) -> User:
        """
        Create a new user with the given data.
        """
        display_name = data.get("display_name")
        if not display_name:
            raise ValueError("Display name is required")

        role_str = data.get("role", "student").upper()
        try:
            role = UserRole[role_str]
        except KeyError:
            role = UserRole.STUDENT

        email = data.get("email")
        line_id = data.get("line_id")
        credits = data.get("credits", 0)

        # Check for duplicates if email or line_id is provided
        if email:
            existing_email = db.session.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError("Email already registered")
                
        if line_id:
            existing_line_id = db.session.query(User).filter(User.line_id == line_id).first()
            if existing_line_id:
                raise ValueError("LINE ID already registered")

        password = data.get("password")
        password_hash = generate_password_hash(password) if password else None

        description = data.get("description")
        level = data.get("level")
        if level is not None and str(level).strip() != "":
            try:
                level = int(level)
            except ValueError:
                level = None
        else:
            level = None

        preferred_venues = data.get("preferred_venues")
        if not isinstance(preferred_venues, list):
            preferred_venues = None

        new_user = User(
            display_name=display_name,
            email=email,
            line_id=line_id,
            role=role,
            credits=credits,
            password_hash=password_hash,
            description=description,
            level=level,
            preferred_venues=preferred_venues
        )

        db.session.add(new_user)
        db.session.commit()
        return new_user
