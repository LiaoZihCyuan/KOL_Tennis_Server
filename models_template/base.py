import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from extensions import db

class BaseModel(db.Model):
    """
    Base model with common fields like UUID id, created_at, and updated_at.
    Inherits from Flask-SQLAlchemy's db.Model.
    Includes soft-delete functionality and basic CRUD methods.
    """
    __abstract__ = True

    # --- Common Columns ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Class-level CRUD methods ---
    @classmethod
    def get(cls, id):
        """Get a record by its primary key, returning None if not found."""
        if id is None:
            return None
        return db.session.get(cls, id)

    @classmethod
    def all(cls):
        """Get all records of this type."""
        return db.session.execute(select(cls)).scalars().all()

    @classmethod
    def filter(cls, **kwargs):
        """
        Filter records by keyword arguments.
        Example: User.filter(name='John', city='New York')
        """
        return db.session.execute(select(cls).filter_by(**kwargs)).scalars().all()

    @classmethod
    def add_all(cls, instances):
        """Adds a list of model instances to the current database session."""
        db.session.add_all(instances)

    @classmethod
    def commit(cls):
        """Commits the current database session."""
        db.session.commit()

    # --- Instance-level methods ---
    def save(self):
        """Adds the current instance to the session and returns the instance."""
        db.session.add(self)
        return self

    def delete(self):
        """Marks the current instance for hard deletion."""
        db.session.delete(self)

    def to_dict(self, exclude=None):
        """
        Serializes the SQLAlchemy model instance to a dictionary.
        'exclude' is a set of attribute names to exclude from the dictionary.
        """
        if exclude is None:
            exclude = set()

        data = {}
        for key in self.__table__.columns.keys():
            if key not in exclude:
                value = getattr(self, key)
                if isinstance(value, uuid.UUID):
                    value = str(value)
                elif isinstance(value, datetime):
                    value = value.isoformat()
                data[key] = value
        return data

    def soft_delete(self):
        """Marks the instance as deleted and adds it to the session."""
        self.deleted_at = datetime.now(timezone.utc)
        db.session.add(self)
