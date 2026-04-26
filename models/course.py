import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class CourseStatus(Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Course(BaseModel):
    __tablename__ = "courses"

    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coach_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CourseStatus] = mapped_column(SQLEnum(CourseStatus), default=CourseStatus.SCHEDULED, nullable=False)

    # Relationships
    coach: Mapped["User"] = relationship("User", back_populates="courses_coached")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="course", cascade="all, delete-orphan")

    __mapper_args__ = {"polymorphic_identity": "course", "concrete": True}