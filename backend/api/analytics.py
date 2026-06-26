"""
api/analytics.py
Historical traffic analytics — wait times, throughput, peak hours.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import List

from db.database import get_db
from db.models import TimingLog, EmergencyEvent
from core.schemas import AnalyticsSummary, WaitTimePoint

router = APIRouter()


@router.get("/{junction_id}/summary", response_model=AnalyticsSummary)
async def get_summary(
    junction_id: int,
    period: str = Query("today", enum=["today", "week", "month"]),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated stats for a junction over a given period."""
    since = _period_start(period)

    # Average wait time
    avg_result = await db.execute(
        select(func.avg(TimingLog.avg_wait))
        .where(TimingLog.junction_id == junction_id)
        .where(TimingLog.timestamp >= since)
    )
    avg_wait = avg_result.scalar() or 0.0

    # Total vehicles
    total_result = await db.execute(
        select(func.sum(TimingLog.vehicle_count))
        .where(TimingLog.junction_id == junction_id)
        .where(TimingLog.timestamp >= since)
    )
    total_vehicles = total_result.scalar() or 0

    # Emergency count
    emg_result = await db.execute(
        select(func.count(EmergencyEvent.id))
        .where(EmergencyEvent.junction_id == junction_id)
        .where(EmergencyEvent.triggered_at >= since)
    )
    emergency_count = emg_result.scalar() or 0

    # Peak hour — find the hour with highest vehicle count
    peak_result = await db.execute(
        select(
            func.date_part("hour", TimingLog.timestamp).label("hour"),
            func.sum(TimingLog.vehicle_count).label("total"),
        )
        .where(TimingLog.junction_id == junction_id)
        .where(TimingLog.timestamp >= since)
        .group_by("hour")
        .order_by(func.sum(TimingLog.vehicle_count).desc())
        .limit(1)
    )
    peak_row = peak_result.fetchone()
    peak_hour = f"{int(peak_row.hour):02d}:00–{int(peak_row.hour)+1:02d}:00" if peak_row else "N/A"

    return AnalyticsSummary(
        junction_id          = junction_id,
        period               = period,
        avg_wait_time_seconds = round(avg_wait, 1),
        peak_hour            = peak_hour,
        total_vehicles       = int(total_vehicles),
        emergency_count      = int(emergency_count),
    )


@router.get("/{junction_id}/wait-time-series", response_model=List[WaitTimePoint])
async def get_wait_time_series(
    junction_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Return hourly average wait times for charting on the dashboard."""
    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        select(
            func.date_trunc("hour", TimingLog.timestamp).label("hour"),
            func.avg(TimingLog.avg_wait).label("avg_wait"),
        )
        .where(TimingLog.junction_id == junction_id)
        .where(TimingLog.timestamp >= since)
        .group_by("hour")
        .order_by("hour")
    )

    return [
        WaitTimePoint(
            timestamp   = row.hour,
            avg_wait    = round(row.avg_wait, 1),
            junction_id = junction_id,
        )
        for row in result.fetchall()
    ]


def _period_start(period: str) -> datetime:
    now = datetime.utcnow()
    if period == "today":  return now.replace(hour=0, minute=0, second=0)
    if period == "week":   return now - timedelta(days=7)
    if period == "month":  return now - timedelta(days=30)
    return now - timedelta(days=1)
