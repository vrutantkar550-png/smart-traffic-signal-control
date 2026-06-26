"""
emergency/preemption.py
Manages the lifecycle of an emergency override:
  - Activates the override in Redis
  - Logs it to PostgreSQL
  - Auto-clears after the configured hold time
  - Allows manual clearance from the dashboard
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import EmergencyEvent
from db.redis_client import set_emergency_flag, get_emergency_flag
from core.schemas import EmergencyStatus
from core.config import settings

logger = logging.getLogger(__name__)


HOLD_TIMES = {
    "ambulance":    settings.EMERGENCY_HOLD_AMBULANCE,
    "fire_truck":   settings.EMERGENCY_HOLD_FIRE,
    "accident":     settings.EMERGENCY_HOLD_ACCIDENT,
    "construction": settings.EMERGENCY_HOLD_CONSTRUCTION,
}


async def activate_emergency(
    junction_id: int,
    emergency_type: str,
    direction: str | None,
    notes: str | None,
    db: AsyncSession,
) -> EmergencyEvent:
    """
    Activate an emergency override:
    1. Set flag in Redis (controller picks it up next tick)
    2. Log the event in PostgreSQL
    3. Schedule auto-clearance
    """
    # Set live flag in Redis
    await set_emergency_flag(junction_id, emergency_type)

    # Log to database
    event = EmergencyEvent(
        junction_id    = junction_id,
        emergency_type = emergency_type,
        direction      = direction,
        notes          = notes,
        status         = EmergencyStatus.ACTIVE,
        triggered_at   = datetime.utcnow(),
    )
    db.add(event)
    await db.flush()  # Get the ID without committing yet
    event_id = event.id
    await db.commit()

    logger.warning(
        f"Emergency ACTIVATED — junction={junction_id} type={emergency_type} "
        f"direction={direction} event_id={event_id}"
    )

    # Schedule auto-clearance in the background
    hold = HOLD_TIMES.get(emergency_type, 60)
    asyncio.create_task(_auto_clear(junction_id, event_id, hold))

    return event


async def clear_emergency(junction_id: int, db: AsyncSession) -> bool:
    """
    Manually clear the emergency override from the dashboard.
    Returns True if there was an active emergency to clear.
    """
    flag = await get_emergency_flag(junction_id)
    if not flag:
        return False

    await set_emergency_flag(junction_id, None)  # Remove from Redis

    # Mark the latest active event as cleared in DB
    result = await db.execute(
        select(EmergencyEvent)
        .where(EmergencyEvent.junction_id == junction_id)
        .where(EmergencyEvent.status == EmergencyStatus.ACTIVE)
        .order_by(EmergencyEvent.triggered_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event:
        event.status     = EmergencyStatus.CLEARED
        event.cleared_at = datetime.utcnow()
        await db.commit()

    logger.info(f"Emergency CLEARED — junction={junction_id}")
    return True


async def _auto_clear(junction_id: int, event_id: int, hold_seconds: int):
    """Background task: waits hold_seconds then clears the emergency automatically."""
    await asyncio.sleep(hold_seconds)

    # Check if still active (manual clear might have already happened)
    flag = await get_emergency_flag(junction_id)
    if flag:
        await set_emergency_flag(junction_id, None)
        logger.info(
            f"Emergency auto-cleared after {hold_seconds}s — "
            f"junction={junction_id} event_id={event_id}"
        )
