import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class which provides automated table name
    and surrogate primary key column.
    """
    pass


class BaseModel(Base):
    __abstract__ = True  # This tells SQLAlchemy not to create a table for BaseModel

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)