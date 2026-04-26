import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, String, Integer, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.course_id"), nullable=False)
    booking_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(SQLEnum(BookingStatus), default=BookingStatus.CONFIRMED, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    student: Mapped["User"] = relationship("User", back_populates="bookings")
    course: Mapped["Course"] = relationship("Course", back_populates="bookings")
    credit_transactions: Mapped[List["CreditTransaction"]] = relationship("CreditTransaction", back_populates="booking", cascade="all, delete-orphan")