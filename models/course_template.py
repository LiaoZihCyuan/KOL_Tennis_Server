from typing import Optional
from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel

class CourseTemplate(BaseModel):
    __tablename__ = "course_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    fee: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, server_default="true")