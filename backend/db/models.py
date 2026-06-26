"""
db/models.py
SQLAlchemy ORM table definitions.
These map directly to PostgreSQL tables.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base
from core.schemas import JunctionType, EmergencyType, EmergencyStatus


class Junction(Base):
    __tablename__ = "junctions"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(120), nullable=False)
    junction_type  = Column(SAEnum(JunctionType), nullable=False)
    latitude       = Column(Float, nullable=False)
    longitude      = Column(Float, nullable=False)
    lane_count     = Column(Integer, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    # One junction → many timing logs and emergency events
    timing_logs  = relationship("TimingLog",   back_populates="junction")
    emergencies  = relationship("EmergencyEvent", back_populates="junction")


class TimingLog(Base):
    """Records every signal phase change with vehicle counts and wait times."""
    __tablename__ = "timing_logs"

    id             = Column(Integer, primary_key=True, index=True)
    junction_id    = Column(Integer, ForeignKey("junctions.id"), nullable=False)
    lane_id        = Column(String(10), nullable=False)   # "N", "S", "E", "W"
    phase          = Column(String(10), nullable=False)   # "GREEN", "RED", etc.
    duration       = Column(Integer, nullable=False)      # seconds the phase lasted
    vehicle_count  = Column(Integer, default=0)
    avg_wait       = Column(Float, default=0.0)
    timestamp      = Column(DateTime(timezone=True), server_default=func.now())

    junction = relationship("Junction", back_populates="timing_logs")


class EmergencyEvent(Base):
    """Records every emergency trigger and clearance."""
    __tablename__ = "emergency_events"

    id              = Column(Integer, primary_key=True, index=True)
    junction_id     = Column(Integer, ForeignKey("junctions.id"), nullable=False)
    emergency_type  = Column(SAEnum(EmergencyType), nullable=False)
    status          = Column(SAEnum(EmergencyStatus), default=EmergencyStatus.ACTIVE)
    direction       = Column(String(10), nullable=True)   # which lane was cleared
    notes           = Column(String(500), nullable=True)
    triggered_at    = Column(DateTime(timezone=True), server_default=func.now())
    cleared_at      = Column(DateTime(timezone=True), nullable=True)

    junction = relationship("Junction", back_populates="emergencies")


class TimingConfig(Base):
    """Per-junction manual timing overrides set from the dashboard."""
    __tablename__ = "timing_configs"

    id           = Column(Integer, primary_key=True, index=True)
    junction_id  = Column(Integer, ForeignKey("junctions.id"), unique=True, nullable=False)
    min_green    = Column(Integer, default=10)
    max_green    = Column(Integer, default=90)
    yellow_time  = Column(Integer, default=3)
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
