from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class which provides automated table name
    and surrogate primary key column.
    """
    pass


class BaseModel(Base):
    __abstract__ = True  # This tells SQLAlchemy not to create a table for BaseModel

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.current_timestamp(), server_default=func.current_timestamp())