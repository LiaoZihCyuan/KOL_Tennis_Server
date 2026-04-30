from typing import Optional
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base

class CreditWallet(Base):
    __tablename__ = "credit_wallets"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    remaining_credits: Mapped[Optional[int]] = mapped_column(Integer, default=0, server_default="0")