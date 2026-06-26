"""
core/schemas.py
Pydantic models used for request/response validation across the API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


# ── Enums ────────────────────────────────────────────────────────────────────

class JunctionType(str, Enum):
    TWO_WAY    = "2way"
    THREE_WAY  = "3way"
    FOUR_WAY   = "4way"


class SignalPhase(str, Enum):
    RED    = "RED"
    YELLOW = "YELLOW"
    GREEN  = "GREEN"


class EmergencyType(str, Enum):
    AMBULANCE    = "ambulance"
    FIRE_TRUCK   = "fire_truck"
    ACCIDENT     = "accident"
    CONSTRUCTION = "construction"


class EmergencyStatus(str, Enum):
    ACTIVE   = "active"
    CLEARED  = "cleared"


# ── Junction ─────────────────────────────────────────────────────────────────

class JunctionBase(BaseModel):
    name: str                  = Field(..., example="Junction A - MG Road")
    junction_type: JunctionType = Field(..., example="4way")
    latitude: float            = Field(..., example=19.9975)
    longitude: float           = Field(..., example=73.7898)
    lane_count: int            = Field(..., ge=2, le=8, example=4)

class JunctionCreate(JunctionBase):
    pass

class JunctionResponse(JunctionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Signal State ─────────────────────────────────────────────────────────────

class LaneState(BaseModel):
    lane_id: str               # e.g. "N", "S", "E", "W"
    phase: SignalPhase
    vehicle_count: int
    green_remaining: Optional[int] = None  # seconds left in green

class JunctionSignalState(BaseModel):
    junction_id: int
    lanes: List[LaneState]
    active_phase_index: int
    emergency_active: bool
    timestamp: datetime


# ── Timing Config ─────────────────────────────────────────────────────────────

class TimingConfig(BaseModel):
    junction_id: int
    min_green: int = Field(10, ge=5, le=30)
    max_green: int = Field(90, ge=30, le=180)
    yellow_time: int = Field(3, ge=2, le=6)


# ── Emergency ────────────────────────────────────────────────────────────────

class EmergencyTrigger(BaseModel):
    emergency_type: EmergencyType
    direction: Optional[str] = Field(None, example="N")  # which lane to clear
    notes: Optional[str]     = None

class EmergencyResponse(BaseModel):
    id: int
    junction_id: int
    emergency_type: EmergencyType
    status: EmergencyStatus
    triggered_at: datetime
    cleared_at: Optional[datetime] = None
    direction: Optional[str]       = None

    class Config:
        from_attributes = True


# ── Analytics ────────────────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    junction_id: int
    period: str                   # "today", "week", "month"
    avg_wait_time_seconds: float
    peak_hour: str                # "08:00–09:00"
    total_vehicles: int
    emergency_count: int


class WaitTimePoint(BaseModel):
    timestamp: datetime
    avg_wait: float
    junction_id: int
