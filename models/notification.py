import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Notification(BaseModel):
    """小編自行新增的公告（教練請假、貴賓來訪等），跟課程請假紀錄一起顯示在
    課表頁面的「通知」面板裡，小編可以隨時刪除。"""
    __tablename__ = "notifications"

    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)

    author: Mapped[Optional["User"]] = relationship("User")
