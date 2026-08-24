import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, String, Integer, ForeignKey, Enum as SQLEnum, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import BaseModel


class CourseStatus(Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Course(BaseModel):
    __tablename__ = "courses"

    coach_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[CourseStatus] = mapped_column(SQLEnum(CourseStatus), default=CourseStatus.SCHEDULED, nullable=False)
    
    # Trial lesson fields
    is_trial: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    trial_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trial_fee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    coach: Mapped["User"] = relationship("User", back_populates="courses_coached")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="course", cascade="all, delete-orphan")

    @classmethod
    def get_courses_in_range(cls, start_date: datetime, end_date: datetime) -> List["Course"]:
        stmt = select(cls).where(
            cls.start_time >= start_date,
            cls.start_time <= end_date,
            cls.deleted_at.is_(None)
        ).order_by(cls.start_time)
        return list(db.session.scalars(stmt))
