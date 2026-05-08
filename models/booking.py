import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, String, ForeignKey, Enum as SQLEnum, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import BaseModel


class BookingStatus(Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    LEAVE_REQUESTED = "leave_requested"
    LEAVE_APPROVED = "leave_approved"
    ATTENDED = "attended"
    ABSENT = "absent"


class Booking(BaseModel):
    __tablename__ = "bookings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), nullable=False)
    booking_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(SQLEnum(BookingStatus), default=BookingStatus.CONFIRMED, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    student: Mapped["User"] = relationship("User", back_populates="bookings")
    course: Mapped["Course"] = relationship("Course", back_populates="bookings")
    credit_transactions: Mapped[List["CreditTransaction"]] = relationship("CreditTransaction", back_populates="booking", cascade="all, delete-orphan")

    @classmethod
    def get_confirmed_for_course(cls, course_id: uuid.UUID) -> List["Booking"]:
        stmt = select(cls).where(
            cls.course_id == course_id,
            cls.status == BookingStatus.CONFIRMED,
            cls.deleted_at.is_(None)
        )
        return list(db.session.scalars(stmt))
