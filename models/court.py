from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel

class Court(BaseModel):
    __tablename__ = "courts"

    name: Mapped[str] = mapped_column(String(50), nullable=False)