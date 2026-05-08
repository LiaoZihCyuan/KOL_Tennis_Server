from sqlalchemy import String, Float, Integer, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from extensions import db
from models.base import BaseModel

# ==========================================
# 1. 卸載策略設定檔 (容器)
# ==========================================
class SheddingProfile(BaseModel):
    __tablename__ = 'shedding_profiles'

    # id, created_at, updated_at, deleted_at 繼承自 BaseModel
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # 關聯：一個 Profile 包含多條規則 (Rules)
    rules: Mapped[list["StrategyRule"]] = relationship(
        "StrategyRule", 
        back_populates="profile", 
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    # 關聯：一個 Profile 可以被多個 Case 使用
    cases: Mapped[list["SimulationCase"]] = relationship(
        "SimulationCase", 
        back_populates="shedding_profile",
        lazy="select"
    )

    def __repr__(self):
        return f'<SheddingProfile {self.name}>'

# ==========================================
# 2. 卸載策略細項規則 (對應 Excel 下半部綠色區塊)
# ==========================================
class StrategyRule(BaseModel):
    __tablename__ = 'strategy_rules'

    # 因為 BaseModel 使用 UUID，這裡的 ForeignKey 也要指明是 UUID
    profile_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey('shedding_profiles.id'), 
        nullable=False
    )
    
    # 規則類型: 'TIME', 'FREQ', 'DFDT'
    rule_type: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # 觸發條件
    trigger_value: Mapped[float] = mapped_column(Float, nullable=False)   # 時間(秒) 或 頻率(Hz)
    trigger_rocof: Mapped[float | None] = mapped_column(Float, nullable=True) # 斜率
    delay_time: Mapped[float] = mapped_column(Float, default=0.0)
    active_time: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0')
    
    # 動作
    shed_load_mw: Mapped[float] = mapped_column(Float, default=0.0)
    trip_gen_mw: Mapped[float] = mapped_column(Float, default=0.0)
    
    # 方便對照原始 Excel 的 row index
    original_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 反向關聯
    profile: Mapped["SheddingProfile"] = relationship("SheddingProfile", back_populates="rules")

    @classmethod
    def find_by_profile(cls, profile_id):
        """Finds all rules associated with a given profile_id."""
        if not profile_id:
            return []
        return cls.filter(profile_id=profile_id)

# ==========================================
# 3. 模擬案例主表 (對應 Excel 上半部物理參數)
# ==========================================
class SimulationCase(BaseModel):
    __tablename__ = 'simulation_cases'

    # --- 基本資訊 ---
    case_name: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_peak: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # --- 系統物理參數 ---
    base_mva: Mapped[float] = mapped_column(Float, default=100.0)
    h_const: Mapped[float] = mapped_column(Float, nullable=False)
    load_damping: Mapped[float] = mapped_column(Float, nullable=False)
    power_factor: Mapped[float] = mapped_column(Float, default=0.9)
    
    # --- 初始狀態 ---
    init_freq: Mapped[float] = mapped_column(Float, default=60.0)
    end_freq: Mapped[float] = mapped_column(Float, default=40.0)
    init_load_mw: Mapped[float] = mapped_column(Float, nullable=False)
    init_gen_mw: Mapped[float] = mapped_column(Float, nullable=False)
    
    # --- 模擬設定 ---
    total_time: Mapped[float] = mapped_column(Float, default=90.0)
    time_step: Mapped[float] = mapped_column(Float, default=0.01)
    freq_step: Mapped[float] = mapped_column(Float, default=0.01)
    
    # --- 輔助服務參數 ---
    d_reg_025: Mapped[float] = mapped_column(Float, default=0.0)
    afc_mw: Mapped[float] = mapped_column(Float, default=0.0)
    s_reg: Mapped[float] = mapped_column(Float, default=0.0)
    e_reg: Mapped[float] = mapped_column(Float, default=0.0)
    
    # --- 關聯 ---
    profile_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey('shedding_profiles.id'),
        nullable=True
    )

    shedding_profile: Mapped["SheddingProfile"] = relationship("SheddingProfile", back_populates="cases")

    @classmethod
    def get_classic_cases_overview(cls):
        """
        Returns an overview of 'classic' cases, identified by their link
        to a SheddingProfile with profile_type 'DEFAULT'.
        """
        from sqlalchemy import select
        # This requires a join to filter by the profile's type
        stmt = select(cls.id, cls.case_name)\
            .join(cls.shedding_profile)\
            .where(SheddingProfile.profile_type == 'DEFAULT')\
            .order_by(cls.case_name)
        return db.session.execute(stmt).all()

    @classmethod
    def get_all_overview(cls):
        """Returns a list of all cases with just their id and name, ordered by name."""
        from sqlalchemy import select
        return db.session.execute(
            select(cls.id, cls.case_name).order_by(cls.case_name)
        ).all()