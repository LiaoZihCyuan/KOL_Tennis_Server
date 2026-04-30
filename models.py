from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from extensions import db

class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    role: Mapped[Optional[str]] = mapped_column(String(20), default="student", server_default="student")
    level: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.current_timestamp(), server_default=func.current_timestamp())

class CourseTemplate(db.Model):
    __tablename__ = "course_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    fee: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, server_default="true")

class CreditWallet(db.Model):
    __tablename__ = "credit_wallets"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    remaining_credits: Mapped[Optional[int]] = mapped_column(Integer, default=0, server_default="0")

class Court(db.Model):
    __tablename__ = "courts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

class Schedule(db.Model):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    court_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courts.id"))
    coach_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    max_capacity: Mapped[Optional[int]] = mapped_column(Integer, default=1, server_default="1")
    description: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("court_id", "start_time", name="unique_court_time"),
        UniqueConstraint("coach_id", "start_time", name="unique_coach_time"),
    )

class Booking(db.Model):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("schedules.id"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    status: Mapped[Optional[str]] = mapped_column(String(20), default="reserved", server_default="reserved")
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.current_timestamp(), server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("schedule_id", "user_id", name="unique_user_booking"),
    )
