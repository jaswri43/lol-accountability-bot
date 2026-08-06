"""SQLAlchemy models and engine/session setup for the bot's SQLite database."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = "sqlite+aiosqlite:///bot.db"

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    discord_id: Mapped[int] = mapped_column(primary_key=True)
    riot_puuid: Mapped[str] = mapped_column(String, unique=True)
    riot_game_name: Mapped[str] = mapped_column(String)
    riot_tag_line: Mapped[str] = mapped_column(String)
    registered_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class ProcessedMatch(Base):
    __tablename__ = "processed_matches"

    match_id: Mapped[str] = mapped_column(String, primary_key=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"), primary_key=True)
    was_loss: Mapped[bool] = mapped_column(Boolean)
    detected_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    match_id: Mapped[str] = mapped_column(String)
    task_description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
