import uuid
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, ForeignKey, JSON, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import BaseModel


class CourseTemplate(BaseModel):
    __tablename__ = "course_templates"

    coach_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Student names / description
    # Linked student user IDs (as strings), so generated courses can create real Bookings for credit tracking.
    # A list (not a single FK) because some templates represent a shared/group class (e.g. "中國醫班").
    student_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time: Mapped[str] = mapped_column(String(10), nullable=False)  # "10:00"
    end_time: Mapped[str] = mapped_column(String(10), nullable=False)  # "11:00"
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="court_out_1", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trial_fee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    coach: Mapped["User"] = relationship("User")

    @classmethod
    def get_active_templates(cls) -> List["CourseTemplate"]:
        stmt = select(cls).where(cls.is_active.is_(True), cls.deleted_at.is_(None)).order_by(cls.day_of_week, cls.start_time)
        return list(db.session.scalars(stmt))
