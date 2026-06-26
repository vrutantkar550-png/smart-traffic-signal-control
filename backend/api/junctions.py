"""
api/junctions.py
CRUD operations for traffic junctions.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from db.database import get_db
from db.models import Junction
from core.schemas import JunctionCreate, JunctionResponse

router = APIRouter()

# Lane layout per junction type
JUNCTION_LANES = {
    "2way": ["N", "S"],
    "3way": ["N", "S", "E"],
    "4way": ["N", "S", "E", "W"],
}


@router.get("/", response_model=List[JunctionResponse])
async def list_junctions(db: AsyncSession = Depends(get_db)):
    """Return all registered junctions."""
    result = await db.execute(select(Junction))
    return result.scalars().all()


@router.post("/", response_model=JunctionResponse, status_code=201)
async def create_junction(
    payload: JunctionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new junction and add it to the live controller."""
    junction = Junction(**payload.model_dump())
    db.add(junction)
    await db.commit()
    await db.refresh(junction)

    # Register with the running signal controller
    from main import signal_controller
    if signal_controller:
        lane_ids = JUNCTION_LANES.get(payload.junction_type.value, ["N", "S", "E", "W"])
        signal_controller.register_junction(junction.id, payload.junction_type.value, lane_ids)

    return junction


@router.get("/{junction_id}", response_model=JunctionResponse)
async def get_junction(junction_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Junction).where(Junction.id == junction_id))
    junction = result.scalar_one_or_none()
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction


@router.delete("/{junction_id}", status_code=204)
async def delete_junction(junction_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Junction).where(Junction.id == junction_id))
    junction = result.scalar_one_or_none()
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    await db.delete(junction)
    await db.commit()
