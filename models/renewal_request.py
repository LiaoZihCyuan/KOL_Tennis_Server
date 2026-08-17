import uuid
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import BaseModel


class RenewalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RenewalRequest(BaseModel):
    __tablename__ = "renewal_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    credits_requested: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    amount_paid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_proof: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[RenewalStatus] = mapped_column(SQLEnum(RenewalStatus), default=RenewalStatus.PENDING, nullable=False)
    admin_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    admin_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    student: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    admin: Mapped[Optional["User"]] = relationship("User", foreign_keys=[admin_user_id])

    @classmethod
    def get_pending_requests(cls):
        stmt = select(cls).where(cls.status == RenewalStatus.PENDING, cls.deleted_at.is_(None)).order_by(cls.created_at.desc())
        return list(db.session.scalars(stmt))
