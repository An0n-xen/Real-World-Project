from __future__ import annotations

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from medagent.config import get_settings
from medagent.logger import get_logger
from medagent.db.models import DiagnosisRecord

logger = get_logger(__name__)

_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    """Initialise the MongoDB connection and Beanie ODM.

    No-op when ``mongodb_enabled`` is ``False``.
    """
    global _client
    settings = get_settings()

    if not settings.mongodb_enabled:
        logger.info("MongoDB disabled — skipping connection")
        return

    if not settings.mongodb_url:
        logger.warning("MONGODB_URL not set — MongoDB features will be unavailable")
        return

    _client = AsyncIOMotorClient(
        settings.mongodb_url,
        tlsCAFile=certifi.where(),
    )

    await init_beanie(
        database=_client[settings.mongodb_database],
        document_models=[DiagnosisRecord],
    )
    logger.info(
        "MongoDB connected  database=%s", settings.mongodb_database,
    )


async def close_db() -> None:
    """Close the MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")
