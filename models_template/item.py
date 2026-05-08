from __future__ import annotations
import uuid

from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel
from .user import User  # Ensure User is imported for the relationship

class Item(BaseModel):
    __tablename__ = "items"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign Key to User
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Relationship to User
    owner: Mapped["User"] = relationship("User", back_populates="items")

    def __repr__(self) -> str:
        return f"<Item(id={self.id}, title='{self.title}')>"

    def to_dict(self, exclude=None):
        if exclude is None:
            exclude = set()
        # Exclude 'deleted_at' by default
        exclude.add('deleted_at')
        return super().to_dict(exclude)
