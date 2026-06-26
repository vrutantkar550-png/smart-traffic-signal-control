"""
api/emergency.py
Endpoints to trigger and clear emergency overrides.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from db.database import get_db
from db.models import EmergencyEvent
from core.schemas import EmergencyTrigger, EmergencyResponse
from emergency.preemption import activate_emergency, clear_emergency

router = APIRouter()


@router.post("/{junction_id}/trigger", response_model=EmergencyResponse, status_code=201)
async def trigger_emergency(
    junction_id: int,
    payload: EmergencyTrigger,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate an emergency override for a junction.
    The signal controller will pick this up on its next tick (within 1 second).

    Body example:
    {
        "emergency_type": "ambulance",
        "direction": "N",
        "notes": "Vehicle approaching from north on MG Road"
    }
    """
    event = await activate_emergency(
        junction_id    = junction_id,
        emergency_type = payload.emergency_type.value,
        direction      = payload.direction,
        notes          = payload.notes,
        db             = db,
    )
    return event


@router.post("/{junction_id}/clear", response_model=dict)
async def clear_emergency_endpoint(
    junction_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually clear an active emergency override.
    The controller auto-clears after the hold time, but operators can clear early.
    """
    was_active = await clear_emergency(junction_id, db)
    if not was_active:
        raise HTTPException(status_code=404, detail="No active emergency found for this junction")
    return {"status": "cleared", "junction_id": junction_id}


@router.get("/{junction_id}/history", response_model=List[EmergencyResponse])
async def get_emergency_history(
    junction_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Return the last N emergency events for a junction."""
    result = await db.execute(
        select(EmergencyEvent)
        .where(EmergencyEvent.junction_id == junction_id)
        .order_by(EmergencyEvent.triggered_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/active/all", response_model=List[dict])
async def get_all_active_emergencies():
    """
    Returns junction IDs with active emergencies.
    The dashboard polls this to show the emergency status map overlay.
    """
    from db.redis_client import get_redis
    r = get_redis()
    keys = await r.keys("emergency:*")
    active = []
    for key in keys:
        val = await r.get(key)
        if val:
            jid = int(key.split(":")[1])
            active.append({"junction_id": jid, "emergency_type": val})
    return active
