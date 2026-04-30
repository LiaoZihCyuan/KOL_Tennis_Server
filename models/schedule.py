from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel

class Schedule(BaseModel):
    __tablename__ = "schedules"

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