from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel

class PowerGeneration(BaseModel):
    __tablename__ = 'power_generations'

    # id, created_at, updated_at are inherited from BaseModel
    
    # Data from the source
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity_mw: Mapped[float] = mapped_column(Float, nullable=False)
    generation_mw: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self):
        return f'<PowerGeneration {self.unit_name} ({self.generation_mw} / {self.capacity_mw} MW)>'
