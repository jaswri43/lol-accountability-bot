"""SQLAlchemy models and engine/session setup for the bot's SQLite database."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, text
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
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Last-known ranked stats per queue, so a new loss's LP change can be
    # computed as a delta against these. Nullable: null until the user's
    # first tracked ranked game in that queue (or if never placed there).
    solo_tier: Mapped[str | None] = mapped_column(nullable=True)
    solo_rank: Mapped[str | None] = mapped_column(nullable=True)
    solo_lp: Mapped[int | None] = mapped_column(nullable=True)
    flex_tier: Mapped[str | None] = mapped_column(nullable=True)
    flex_rank: Mapped[str | None] = mapped_column(nullable=True)
    flex_lp: Mapped[int | None] = mapped_column(nullable=True)
    # Pity meter driving the task-severity system (see bot/severity.py) and
    # the per-user opt-in toggle for it. Unused/frozen for users who never
    # turn severity_mode on.
    pity: Mapped[float] = mapped_column(default=0.0)
    severity_mode: Mapped[bool] = mapped_column(Boolean, default=False)


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
    # Nullable: only set for tasks posted after reaction-based completion was
    # added, and only for tasks that made it into the announce channel.
    message_id: Mapped[int | None] = mapped_column(nullable=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(nullable=True)


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    description: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # Severity tier this task is tagged for ("low"/"medium"/"high"), used
    # when its owner has severity_mode on. Nullable: untagged tasks are
    # tier-agnostic and only used as a fallback in severity mode.
    tier: Mapped[str | None] = mapped_column(nullable=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_column_if_missing(conn, "tasks", "message_id", "INTEGER")
        await _add_column_if_missing(conn, "tasks", "last_reminded_at", "DATETIME")
        await _add_column_if_missing(conn, "users", "muted", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "users", "solo_tier", "VARCHAR")
        await _add_column_if_missing(conn, "users", "solo_rank", "VARCHAR")
        await _add_column_if_missing(conn, "users", "solo_lp", "INTEGER")
        await _add_column_if_missing(conn, "users", "flex_tier", "VARCHAR")
        await _add_column_if_missing(conn, "users", "flex_rank", "VARCHAR")
        await _add_column_if_missing(conn, "users", "flex_lp", "INTEGER")
        await _add_column_if_missing(conn, "users", "pity", "REAL DEFAULT 0")
        await _add_column_if_missing(conn, "users", "severity_mode", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "task_templates", "tier", "VARCHAR")


async def _add_column_if_missing(conn, table: str, column: str, column_type: str) -> None:
    """create_all only creates missing tables, not missing columns on tables
    that already exist -- this adds a column via ALTER TABLE if it's not there
    yet, so existing rows in an existing bot.db pick up new fields safely."""
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = {row[1] for row in result.fetchall()}
    if column not in columns:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))


async def complete_task(session: AsyncSession, task: Task) -> None:
    """Shared by /done and the persistent Mark Done button so completion is
    defined in exactly one place."""
    task.status = "done"
    task.completed_at = datetime.now(timezone.utc)
