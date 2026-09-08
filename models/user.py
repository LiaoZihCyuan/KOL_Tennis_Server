import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import String, Integer, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class UserRole(Enum):
    STUDENT = "student"
    COACH = "coach"
    ADMIN = "admin"


class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(BaseModel):
    __tablename__ = "users"

    line_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    # 登入帳號。刻意跟 display_name 分開：display_name 是課表上顯示的名字，改名很常見，
    # 而且沒有唯一性（名冊裡本來就有同名的人），拿它當登入識別會抓錯人。只有真的會
    # 登入的使用者（有密碼者）才需要 username，純排課名冊的學生留 NULL 即可
    # （Postgres 的 unique 允許多筆 NULL）。
    username: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False)
    # credits / lesson_count are a manually-managed balance (topped up via
    # renewals, adjusted directly in 使用者管理) — courses no longer have a
    # point cost, so nothing here is auto-deducted at booking/checkin time.
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lesson_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # New fields
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gender: Mapped[Optional[Gender]] = mapped_column(SQLEnum(Gender), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color for coaches, e.g. #3B82F6
    line_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    preferred_venues: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="student", cascade="all, delete-orphan")
    credit_transactions: Mapped[List["CreditTransaction"]] = relationship(
        "CreditTransaction", foreign_keys="[CreditTransaction.user_id]", back_populates="student", cascade="all, delete-orphan"
    )
    courses_coached: Mapped[List["Course"]] = relationship("Course", back_populates="coach", cascade="all, delete-orphan")
    admin_transactions: Mapped[List["CreditTransaction"]] = relationship("CreditTransaction", foreign_keys="[CreditTransaction.admin_user_id]")

    @classmethod
    def get_users_by_role(cls, role: UserRole) -> List["User"]:
        from extensions import db
        from sqlalchemy import select
        stmt = select(cls).where(cls.role == role, cls.deleted_at.is_(None))
        return list(db.session.scalars(stmt))

