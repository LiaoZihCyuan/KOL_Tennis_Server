import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
from extensions import db
from models.user import User, UserRole, Gender
from models.booking import Booking, BookingStatus
from models.course import Course
from services.course_service import to_taipei
from utils.colors import suggest_distinct_color


class UserService:
    @staticmethod
    def _parse_level(level: Any) -> Optional[int]:
        if level is None or isinstance(level, bool) or str(level).strip() == "":
            return None
        try:
            number = int(level)
        except (ValueError, TypeError, OverflowError):
            return None
        return number if UserService._INT_MIN <= number <= UserService._INT_MAX else None

    @staticmethod
    def _normalize_username(value: Any) -> Optional[str]:
        """空字串一律存成 NULL——unique 欄位允許多筆 NULL，但只允許一筆空字串。"""
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    # 文字欄位的長度上限，跟 models/user.py 的 String(n) 一致。
    _MAX_LENGTHS = {
        "display_name": ("顯示名稱", 255),
        "username": ("登入帳號", 255),
        "nickname": ("暱稱", 100),
        "phone": ("電話", 20),
        "email": ("Email", 255),
        "line_id": ("LINE ID", 255),
        "line_display_name": ("LINE 顯示名稱", 255),
        "color": ("代表色", 7),
        "description": ("說明", 500),
    }

    _TEXT_LABELS = {
        **{field: label for field, (label, _) in _MAX_LENGTHS.items()},
        "notes": "備註",
        "password": "密碼",
        "role": "角色",
        "gender": "性別",
    }
    _INT_MIN, _INT_MAX = -2147483648, 2147483647

    @staticmethod
    def _clean_text_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """把文字欄位整理成資料庫存得進去的字串，回傳新的 dict（不改呼叫端的）。

        - 數字（例如 phone 傳成整數）轉成字串；陣列、物件、布林值直接拒絕。
        - 去掉 PostgreSQL 存不進去的 NUL 字元與不成對的 surrogate（半個 emoji）。
        密碼只檢查型別，內容不動。
        """
        cleaned = dict(data)
        for field, label in UserService._TEXT_LABELS.items():
            value = cleaned.get(field)
            if value is None:
                continue
            # 只接受字串與整數；小數（含 NaN／Infinity）轉成字串沒有意義
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise ValueError(f"{label} 格式不正確")
            if field == "password":
                if not isinstance(value, str):
                    raise ValueError(f"{label} 格式不正確")
                try:
                    value.encode("utf-8")
                except UnicodeEncodeError:
                    raise ValueError(f"{label} 含有無法使用的字元")
                continue
            value = str(value).replace("\x00", "")
            cleaned[field] = value.encode("utf-8", "ignore").decode("utf-8")
        return cleaned

    @staticmethod
    def _parse_int(value: Any, label: str) -> int:
        """點數／堂數：不是整數或超出資料庫範圍時丟出中文錯誤，而不是 500。"""
        if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
            raise ValueError(f"{label} 必須是整數")
        try:
            number = int(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"{label} 必須是整數")
        if not UserService._INT_MIN <= number <= UserService._INT_MAX:
            raise ValueError(f"{label} 數值過大")
        return number

    @staticmethod
    def _clean_venues(value: Any) -> Optional[List[str]]:
        """偏好場地：只接受字串陣列（JSON 欄位存不了 NaN／Infinity 之類的值）。"""
        if not isinstance(value, list):
            return None
        if len(value) > 20 or not all(isinstance(v, str) and len(v) <= 100 for v in value):
            raise ValueError("偏好場地 格式不正確")
        return [v.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8") for v in value]

    @staticmethod
    def _commit() -> None:
        """兩個請求同時搶同一個 LINE ID／帳號／Email 時，事前檢查都會通過，
        要靠資料庫的 unique 限制擋下後者；把它轉成 400 而不是 500。"""
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValueError("LINE ID、登入帳號或 Email 與其他使用者重複，請重新整理後再試")

    @staticmethod
    def _assert_lengths(data: Dict[str, Any]) -> None:
        """超過欄位長度時丟出中文錯誤，而不是讓資料庫截斷錯誤變成 500。"""
        for field, (label, limit) in UserService._MAX_LENGTHS.items():
            value = data.get(field)
            if value is not None and len(str(value)) > limit:
                raise ValueError(f"{label} 最多 {limit} 個字")

    @staticmethod
    def _assert_unique(column, value: Optional[str], message: str, exclude_user_id: Optional[uuid.UUID] = None) -> None:
        """unique 欄位重複時丟出中文錯誤，而不是讓資料庫的 unique 違反變成 500。

        已軟刪除的使用者也要比對：資料庫的 unique 限制不分是否刪除。
        """
        if not value:
            return
        stmt = db.session.query(User).filter(column == value)
        if exclude_user_id:
            stmt = stmt.filter(User.id != exclude_user_id)
        with db.session.no_autoflush:
            if stmt.first():
                raise ValueError(message)

    @staticmethod
    def _assert_line_id_available(line_id: Optional[str], exclude_user_id: Optional[uuid.UUID] = None) -> None:
        UserService._assert_unique(User.line_id, line_id, "此 LINE ID 已被使用", exclude_user_id)

    @staticmethod
    def _assert_email_available(email: Optional[str], exclude_user_id: Optional[uuid.UUID] = None) -> None:
        UserService._assert_unique(User.email, email, "此 Email 已被使用", exclude_user_id)

    @staticmethod
    def _assert_username_available(username: Optional[str], exclude_user_id: Optional[uuid.UUID] = None) -> None:
        UserService._assert_unique(
            User.username, username, f"帳號「{username}」已被使用，請換一個", exclude_user_id
        )

    @staticmethod
    def get_all_users() -> List[User]:
        return db.session.query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at.desc()).all()

    @staticmethod
    def get_coaches() -> List[User]:
        return User.get_users_by_role(UserRole.COACH)

    @staticmethod
    def suggest_coach_color() -> str:
        """A color as different as possible from every active coach's color."""
        return suggest_distinct_color(c.color for c in UserService.get_coaches())

    @staticmethod
    def get_students() -> List[User]:
        return User.get_users_by_role(UserRole.STUDENT)

    @staticmethod
    def create_user(data: Dict[str, Any]) -> User:
        data = UserService._clean_text_fields(data)
        display_name = data.get("display_name")
        if not display_name:
            raise ValueError("請填寫顯示名稱")
        UserService._assert_lengths(data)

        role_str = (data.get("role") or "student").upper()
        try:
            role = UserRole[role_str]
        except KeyError:
            role = UserRole.STUDENT

        # 空字串存成 NULL：email 是 unique，只允許一筆空字串。
        email = UserService._normalize_username(data.get("email"))
        # 空字串存成 NULL：line_id 是 unique，只允許一筆空字串。
        line_id = UserService._normalize_username(data.get("line_id"))
        phone = data.get("phone")
        credits = data.get("credits")
        credits = UserService._parse_int(credits, "點數") if credits not in (None, "") else 0
        # lesson_count (堂數) defaults to the same number as credits (點數) when
        # not given separately — for the common 1 小時 = 1 點 = 1 堂 case this
        # just works; admins can override it if this batch of credits was
        # bought for longer lessons.
        lesson_count = data.get("lesson_count")
        lesson_count = UserService._parse_int(lesson_count, "堂數") if lesson_count not in (None, "") else credits

        # Check for duplicates if email, line_id, or phone is provided
        UserService._assert_email_available(email)
        UserService._assert_line_id_available(line_id)

        if phone:
            existing_phone = db.session.query(User).filter(User.phone == phone, User.deleted_at.is_(None)).first()
            if existing_phone:
                raise ValueError("此電話號碼已被使用")

        # Default password to the phone number when left blank, matching the
        # existing convention (see seed_data.py) so admins can hand out an
        # account without typing a separate password.
        password = data.get("password") or phone
        password_hash = generate_password_hash(password) if password else None

        # 登入帳號：沒指定就沿用顯示名稱（跟舊行為一致，小編習慣用「王教練」登入）。
        # 只有真的會登入的人（有密碼）才給帳號，純名冊學生留 NULL 不佔用帳號名稱。
        username = UserService._normalize_username(data.get("username"))
        if not username and password_hash:
            username = UserService._normalize_username(display_name)
        UserService._assert_username_available(username)

        gender_val = None
        if data.get("gender"):
            try:
                gender_val = Gender(data["gender"].lower())
            except ValueError:
                pass

        new_user = User(
            display_name=display_name,
            username=username,
            nickname=data.get("nickname"),
            gender=gender_val,
            phone=phone,
            email=email,
            line_id=line_id,
            line_display_name=data.get("line_display_name"),
            role=role,
            credits=credits,
            lesson_count=lesson_count,
            # 教練沒指定代表色就自動配一個跟現有教練差異最大的顏色
            color=data.get("color") or (UserService.suggest_coach_color() if role == UserRole.COACH else None),
            notes=data.get("notes"),
            password_hash=password_hash,
            description=data.get("description"),
            level=UserService._parse_level(data.get("level")),
            preferred_venues=UserService._clean_venues(data.get("preferred_venues"))
        )

        db.session.add(new_user)
        UserService._commit()
        return new_user

    @staticmethod
    def update_user(user_id: uuid.UUID, data: Dict[str, Any]) -> Optional[User]:
        user = User.get(user_id)
        if not user or user.deleted_at is not None:
            return None

        data = UserService._clean_text_fields(data)
        UserService._assert_lengths(data)

        # Fields to update
        if "display_name" in data and data["display_name"]:
            user.display_name = data["display_name"]
        if "nickname" in data:
            user.nickname = data["nickname"]
        if "phone" in data:
            user.phone = data["phone"]
        if "email" in data:
            # 空字串存成 NULL，理由同 line_id
            new_email = UserService._normalize_username(data["email"])
            UserService._assert_email_available(new_email, exclude_user_id=user.id)
            user.email = new_email
        if "line_id" in data:
            # 空字串存成 NULL：line_id 是 unique，只允許一筆空字串，
            # 否則第二個沒填 LINE ID 的人存檔就會撞到 unique 變成 500。
            new_line_id = UserService._normalize_username(data["line_id"])
            UserService._assert_line_id_available(new_line_id, exclude_user_id=user.id)
            user.line_id = new_line_id
        if "line_display_name" in data:
            user.line_display_name = data["line_display_name"]
        if "credits" in data and data["credits"] is not None:
            user.credits = UserService._parse_int(data["credits"], "點數")
        if "lesson_count" in data and data["lesson_count"] is not None:
            user.lesson_count = UserService._parse_int(data["lesson_count"], "堂數")
        if "color" in data:
            user.color = data["color"]
        if "notes" in data:
            user.notes = data["notes"]
        if "description" in data:
            user.description = data["description"]
        if "level" in data:
            user.level = UserService._parse_level(data["level"])
        if "preferred_venues" in data and isinstance(data["preferred_venues"], list):
            user.preferred_venues = UserService._clean_venues(data["preferred_venues"])
        if "gender" in data and data["gender"]:
            try:
                user.gender = Gender(data["gender"].lower())
            except ValueError:
                pass
        if "username" in data:
            new_username = UserService._normalize_username(data["username"])
            UserService._assert_username_available(new_username, exclude_user_id=user.id)
            user.username = new_username
        if "password" in data and data["password"]:
            user.password_hash = generate_password_hash(data["password"])
            # 設了密碼就代表這個人要能登入，但沒帳號的話登不進來（登入不再比對
            # display_name），所以補一個預設帳號，避免建立出登不進去的帳號。
            if not user.username:
                fallback = UserService._normalize_username(user.display_name)
                try:
                    UserService._assert_username_available(fallback, exclude_user_id=user.id)
                    user.username = fallback
                except ValueError:
                    raise ValueError(
                        f"已設定密碼，但預設帳號「{fallback}」已被使用，請另外指定「登入帳號」"
                    )

        UserService._commit()
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
