"""
core/config.py
Loads all environment variables from .env file.
Access anywhere via: from core.config import settings
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Smart Traffic Signal Control"
    DEBUG: bool = False

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/traffic_db"

    # Redis (real-time signal state cache)
    REDIS_URL: str = "redis://localhost:6379"

    # CORS — React frontend origin
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # ML model file paths (relative to backend/)
    RL_MODEL_PATH: str = "models/traffic_rl_agent.zip"
    YOLO_MODEL_PATH: str = "models/yolo_detector.pt"

    # Signal timing limits (seconds)
    MIN_GREEN_TIME: int = 10
    MAX_GREEN_TIME: int = 90
    YELLOW_TIME: int = 3
    ALL_RED_TIME: int = 2  # Safety gap between phase switches

    # Emergency override durations (seconds)
    EMERGENCY_HOLD_AMBULANCE: int = 60
    EMERGENCY_HOLD_FIRE: int = 90
    EMERGENCY_HOLD_ACCIDENT: int = 120
    EMERGENCY_HOLD_CONSTRUCTION: int = 180

    # Controller tick rate (how often the loop runs, in seconds)
    CONTROLLER_TICK: float = 1.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
