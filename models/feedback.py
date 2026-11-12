import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Feedback(BaseModel):
    """小編／教練從網站送出的意見回饋。網站只負責寫入（沒有任何讀取或管理的
    頁面與 API）；status、resolved_at、resolution_note 由開發端直接在資料庫
    更新，用來標記這筆回饋處理完了沒。"""
    __tablename__ = "feedback"

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 送出當下的角色與所在頁面，之後重現問題時不必再回頭問對方
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    page_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_OPEN, server_default=STATUS_OPEN
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    author: Mapped[Optional["User"]] = relationship("User")
