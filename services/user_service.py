import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from werkzeug.security import generate_password_hash
from extensions import db
from models.user import User, UserRole, Gender
from models.booking import Booking, BookingStatus
from models.course import Course
from services.course_service import to_taipei


class UserService:
    @staticmethod
    def _parse_level(level: Any) -> Optional[int]:
        if level is None or str(level).strip() == "":
            return None
        try:
            return int(level)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def get_all_users() -> List[User]:
        return db.session.query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at.desc()).all()

    @staticmethod
    def get_coaches() -> List[User]:
        return User.get_users_by_role(UserRole.COACH)

    @staticmethod
    def get_students() -> List[User]:
        return User.get_users_by_role(UserRole.STUDENT)

    @staticmethod
    def create_user(data: Dict[str, Any]) -> User:
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
        phone = data.get("phone")
        credits = data.get("credits", 0)
        # lesson_count (堂數) defaults to the same number as credits (點數) when
        # not given separately — for the common 1 小時 = 1 點 = 1 堂 case this
        # just works; admins can override it if this batch of credits was
        # bought for longer lessons.
        lesson_count = data.get("lesson_count")
        lesson_count = int(lesson_count) if lesson_count not in (None, "") else credits

        # Check for duplicates if email, line_id, or phone is provided
        if email:
            existing_email = db.session.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
            if existing_email:
                raise ValueError("Email already registered")
                
        if line_id:
            existing_line_id = db.session.query(User).filter(User.line_id == line_id, User.deleted_at.is_(None)).first()
            if existing_line_id:
                raise ValueError("LINE ID already registered")

        if phone:
            existing_phone = db.session.query(User).filter(User.phone == phone, User.deleted_at.is_(None)).first()
            if existing_phone:
                raise ValueError("此電話號碼已被使用")

        # Default password to the phone number when left blank, matching the
        # existing convention (see seed_data.py) so admins can hand out an
        # account without typing a separate password.
        password = data.get("password") or phone
        password_hash = generate_password_hash(password) if password else None

        gender_val = None
        if data.get("gender"):
            try:
                gender_val = Gender(data["gender"].lower())
            except ValueError:
                pass

        new_user = User(
            display_name=display_name,
            nickname=data.get("nickname"),
            gender=gender_val,
            phone=phone,
            email=email,
            line_id=line_id,
            line_display_name=data.get("line_display_name"),
            role=role,
            credits=credits,
            lesson_count=lesson_count,
            color=data.get("color"),
            notes=data.get("notes"),
            password_hash=password_hash,
            description=data.get("description"),
            level=UserService._parse_level(data.get("level")),
            preferred_venues=data.get("preferred_venues") if isinstance(data.get("preferred_venues"), list) else None
        )

        db.session.add(new_user)
        db.session.commit()
        return new_user

    @staticmethod
    def update_user(user_id: uuid.UUID, data: Dict[str, Any]) -> Optional[User]:
        user = User.get(user_id)
        if not user or user.deleted_at is not None:
            return None

        # Fields to update
        if "display_name" in data and data["display_name"]:
            user.display_name = data["display_name"]
        if "nickname" in data:
            user.nickname = data["nickname"]
        if "phone" in data:
            user.phone = data["phone"]
        if "email" in data:
            user.email = data["email"]
        if "line_id" in data:
            user.line_id = data["line_id"]
        if "line_display_name" in data:
            user.line_display_name = data["line_display_name"]
        if "credits" in data and data["credits"] is not None:
            user.credits = int(data["credits"])
        if "lesson_count" in data and data["lesson_count"] is not None:
            user.lesson_count = int(data["lesson_count"])
        if "color" in data:
            user.color = data["color"]
        if "notes" in data:
            user.notes = data["notes"]
        if "description" in data:
            user.description = data["description"]
        if "level" in data:
            user.level = UserService._parse_level(data["level"])
        if "preferred_venues" in data and isinstance(data["preferred_venues"], list):
            user.preferred_venues = data["preferred_venues"]
        if "gender" in data and data["gender"]:
            try:
                user.gender = Gender(data["gender"].lower())
            except ValueError:
                pass
        if "password" in data and data["password"]:
            user.password_hash = generate_password_hash(data["password"])

        db.session.commit()
        return user

    @staticmethod
    def get_student_attendance_stats() -> List[Dict[str, Any]]:
        """
        Calculate remaining credits and list of attendance dates for each student.
        """
        students = User.get_users_by_role(UserRole.STUDENT)
        stats = []

        for student in students:
            # Query all bookings for this student
            bookings = db.session.query(Booking).join(Course).filter(
                Booking.user_id == student.id,
                Booking.deleted_at.is_(None),
                Course.deleted_at.is_(None)
            ).order_by(Course.start_time.desc()).all()

            attended_dates = []
            absent_dates = []
            leave_dates = []

            for b in bookings:
                c = b.course
                # 一律轉台北時間再顯示，否則出缺席紀錄會顯示 UTC 時間（台北
                # 10:00 的課會顯示成 02:00），跟行事曆上看到的時間對不起來。
                date_str = to_taipei(c.start_time).strftime("%Y-%m-%d %H:%M") if c else ""
                coach_name = c.coach.display_name if c and c.coach else "未知"
                entry = f"{date_str} ({coach_name})"

                if b.status == BookingStatus.ATTENDED:
                    attended_dates.append(entry)
                elif b.status == BookingStatus.ABSENT:
                    absent_dates.append(entry)
                elif b.status in (BookingStatus.LEAVE_REQUESTED, BookingStatus.LEAVE_APPROVED):
                    leave_dates.append(entry)
                elif b.status == BookingStatus.CONFIRMED:
                    # If course passed and was confirmed, treated as attended
                    if c and c.start_time < datetime.now(c.start_time.tzinfo):
                        attended_dates.append(entry)

            stats.append({
                "student_id": str(student.id),
                "display_name": student.display_name,
                "nickname": student.nickname,
                "phone": student.phone,
                "line_id": student.line_id,
                "credits": student.credits,
                "lesson_count": student.lesson_count,
                "attended_count": len(attended_dates),
                "attended_dates": attended_dates,
                "absent_count": len(absent_dates),
                "absent_dates": absent_dates,
                "leave_count": len(leave_dates),
                "leave_dates": leave_dates
            })

        return stats
