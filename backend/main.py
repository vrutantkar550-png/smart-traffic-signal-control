"""
Smart Traffic Signal Control System
Main FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from api import signals, junctions, emergency, analytics, websocket
from engine.controller import SignalController
from db.database import init_db
from core.config import settings


# Global signal controller instance
signal_controller: SignalController = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global signal_controller

    # Initialize database tables
    await init_db()

    # Start the signal control loop in background
    signal_controller = SignalController()
    asyncio.create_task(signal_controller.run_loop())
    print("Signal controller started.")

    yield  # App runs here

    # Shutdown: stop the control loop
    signal_controller.stop()
    print("Signal controller stopped.")


app = FastAPI(
    title="Smart Traffic Signal Control API",
    description="AI-powered adaptive traffic signal management with emergency override",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend (React) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route groups
app.include_router(signals.router,    prefix="/api/signals",    tags=["signals"])
app.include_router(junctions.router,  prefix="/api/junctions",  tags=["junctions"])
app.include_router(emergency.router,  prefix="/api/emergency",  tags=["emergency"])
app.include_router(analytics.router,  prefix="/api/analytics",  tags=["analytics"])
app.include_router(websocket.router,  prefix="/ws",             tags=["websocket"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

