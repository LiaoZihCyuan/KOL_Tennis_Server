import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class UserRole(Enum):
    STUDENT = "student"
    COACH = "coach"
    ADMIN = "admin"


class User(BaseModel):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    line_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    # For students: bookings made by this user
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="student", cascade="all, delete-orphan")
    # For students: credit transactions related to this user
    credit_transactions: Mapped[List["CreditTransaction"]] = relationship(
        "CreditTransaction", foreign_keys="[CreditTransaction.user_id]", back_populates="student", cascade="all, delete-orphan"
    )
    # For coaches: courses coached by this user
    courses_coached: Mapped[List["Course"]] = relationship("Course", back_populates="coach", cascade="all, delete-orphan")
    # For admins: credit transactions performed by this admin
    admin_transactions: Mapped[List["CreditTransaction"]] = relationship("CreditTransaction", foreign_keys="[CreditTransaction.admin_user_id]")

    __mapper_args__ = {"polymorphic_identity": "user", "concrete": True}