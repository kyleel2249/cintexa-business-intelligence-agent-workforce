"""Initialise database schema."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from config.settings import get_settings
from database.models import Base


async def init_models() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=settings.debug)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("CINTEXA BI database schema created.")


if __name__ == "__main__":
    asyncio.run(init_models())
