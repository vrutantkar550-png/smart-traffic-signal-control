"""
api/signals.py
Endpoints for reading and manually controlling signal states.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.redis_client import get_signal_state, set_vehicle_counts
from core.schemas import TimingConfig, JunctionSignalState

router = APIRouter()


@router.get("/{junction_id}/state", response_model=dict)
async def get_signal_state_endpoint(junction_id: int):
    """Get the current live signal state of a junction."""
    state = await get_signal_state(junction_id)
    if not state:
        raise HTTPException(status_code=404, detail="Junction state not found or controller not running")
    return state


@router.post("/{junction_id}/vehicle-counts")
async def update_vehicle_counts(junction_id: int, counts: dict):
    """
    Receive vehicle counts from the detection system (camera / YOLO).
    In production, the camera server calls this every ~1 second.
    Body example: {"N": 12, "S": 4, "E": 7, "W": 3}
    """
    await set_vehicle_counts(junction_id, counts)
    return {"status": "updated", "junction_id": junction_id}


@router.put("/{junction_id}/timing", response_model=dict)
async def update_timing_config(
    junction_id: int,
    config: TimingConfig,
    db: AsyncSession = Depends(get_db),
):
    """Update min/max green time for a junction from the dashboard."""
    from db.models import TimingConfig as TimingConfigModel
    from sqlalchemy import select

    result = await db.execute(
        select(TimingConfigModel).where(TimingConfigModel.junction_id == junction_id)
    )
    tc = result.scalar_one_or_none()

    if tc:
        tc.min_green   = config.min_green
        tc.max_green   = config.max_green
        tc.yellow_time = config.yellow_time
    else:
        tc = TimingConfigModel(
            junction_id = junction_id,
            min_green   = config.min_green,
            max_green   = config.max_green,
            yellow_time = config.yellow_time,
        )
        db.add(tc)

    await db.commit()
    return {"status": "timing updated", "junction_id": junction_id}
