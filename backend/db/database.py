"""
db/database.py
Async SQLAlchemy engine, session factory, and table initialisation.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings


# Create the async engine (connects to PostgreSQL)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,       # Logs SQL queries when DEBUG=True
    pool_size=10,
    max_overflow=20,
)

# Session factory — use this to get a DB session in route handlers
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """All ORM models inherit from this."""
    pass


async def init_db():
    """Create all tables on startup if they don't exist."""
    from db import models  # Import models so Base knows about them
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialised.")


async def get_db():
    """
    FastAPI dependency — yields a DB session per request and closes it after.
    Usage in route:  db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

