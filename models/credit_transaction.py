import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, String, Integer, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class TransactionType(Enum):
    PURCHASE = "purchase"
    DEDUCTION = "deduction"
    REFUND_LEAVE = "refund_leave"
    ADMIN_ADD = "admin_add"


class CreditTransaction(BaseModel):
    __tablename__ = "credit_transactions"

    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(SQLEnum(TransactionType), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    related_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"), nullable=True)
    admin_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    student: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="credit_transactions")
    admin: Mapped[Optional["User"]] = relationship("User", foreign_keys=[admin_user_id], back_populates="admin_transactions")
    booking: Mapped[Optional["Booking"]] = relationship("Booking", back_populates="credit_transactions")