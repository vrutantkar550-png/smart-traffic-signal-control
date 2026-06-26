"""
db/redis_client.py
Redis connection for storing live signal state.
Redis is used instead of PostgreSQL for real-time data because it's
in-memory and extremely fast (microsecond reads/writes).
"""

import redis.asyncio as aioredis
import json
from core.config import settings


# Single shared Redis connection pool
redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=True,
)


def get_redis() -> aioredis.Redis:
    """Returns a Redis client using the shared pool."""
    return aioredis.Redis(connection_pool=redis_pool)


# ── Helper functions ──────────────────────────────────────────────────────────

async def set_signal_state(junction_id: int, state: dict, ttl: int = 30):
    """
    Save the current signal state for a junction.
    TTL=30 means stale data auto-expires after 30 seconds if the controller dies.
    """
    r = get_redis()
    key = f"signal_state:{junction_id}"
    await r.set(key, json.dumps(state), ex=ttl)


async def get_signal_state(junction_id: int) -> dict | None:
    """Read the current signal state for a junction."""
    r = get_redis()
    key = f"signal_state:{junction_id}"
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def set_emergency_flag(junction_id: int, emergency_type: str | None):
    """
    Set or clear the emergency flag for a junction.
    The signal controller checks this every tick.
    """
    r = get_redis()
    key = f"emergency:{junction_id}"
    if emergency_type:
        await r.set(key, emergency_type, ex=600)  # auto-expire after 10 min
    else:
        await r.delete(key)


async def get_emergency_flag(junction_id: int) -> str | None:
    """Returns the active emergency type, or None if no emergency."""
    r = get_redis()
    return await r.get(f"emergency:{junction_id}")


async def set_vehicle_counts(junction_id: int, counts: dict):
    """Store latest vehicle counts per lane, e.g. {"N": 12, "S": 3, "E": 7, "W": 5}"""
    r = get_redis()
    await r.set(f"vehicle_counts:{junction_id}", json.dumps(counts), ex=10)


async def get_vehicle_counts(junction_id: int) -> dict:
    r = get_redis()
    raw = await r.get(f"vehicle_counts:{junction_id}")
    return json.loads(raw) if raw else {}
