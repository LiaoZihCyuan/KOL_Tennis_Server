from typing import Optional
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel

class Booking(BaseModel):
    __tablename__ = "bookings"

    schedule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("schedules.id"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    status: Mapped[Optional[str]] = mapped_column(String(20), default="reserved", server_default="reserved")
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("schedule_id", "user_id", name="unique_user_booking"),
    )