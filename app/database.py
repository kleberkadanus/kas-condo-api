from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://kas:***@localhost:5432/kas_condo")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables():
    async with engine.begin() as conn:
        try:
            await conn.run_sync(SQLModel.metadata.create_all)
        except Exception:
            pass
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS camera_ids TEXT DEFAULT ''",
            "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_url TEXT DEFAULT ''",
        ]
        for stmt in migrations:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
