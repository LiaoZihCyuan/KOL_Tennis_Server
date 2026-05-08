import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import String, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class UserRole(Enum):
    STUDENT = "student"
    COACH = "coach"
    ADMIN = "admin"


class User(BaseModel):
    __tablename__ = "users"

    line_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="student", cascade="all, delete-orphan")
    credit_transactions: Mapped[List["CreditTransaction"]] = relationship(
        "CreditTransaction", foreign_keys="[CreditTransaction.user_id]", back_populates="student", cascade="all, delete-orphan"
    )
    courses_coached: Mapped[List["Course"]] = relationship("Course", back_populates="coach", cascade="all, delete-orphan")
    admin_transactions: Mapped[List["CreditTransaction"]] = relationship("CreditTransaction", foreign_keys="[CreditTransaction.admin_user_id]")
