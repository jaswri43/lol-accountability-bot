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
    # Pity meter driving the task-severity system (see bot/severity.py).
    # Frozen at 0 until the user tags a Medium/High task with /addtask --
    # see severity.has_opted_into_severity, there's no separate toggle.
    pity: Mapped[float] = mapped_column(default=0.0)
    # Unused as of the always-on severity redesign -- see init_db() below
    # for why the column itself is kept rather than dropped.
    severity_mode: Mapped[bool] = mapped_column(Boolean, default=False)


class ProcessedMatch(Base):
    __tablename__ = "processed_matches"

    match_id: Mapped[str] = mapped_column(String, primary_key=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"), primary_key=True)
    was_loss: Mapped[bool] = mapped_column(Boolean)
    detected_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # Everything below is populated only for ranked matches (queue_id in
    # riot_api.RANKED_QUEUE_IDS), starting from when these columns were
    # added -- NULL for older rows and for non-ranked matches (which only
    # ever got a placeholder row here to avoid reprocessing them; their
    # was_loss is meaningless, always False regardless of actual result).
    # Never backfilled -- powers the match-history feed, per-queue win/loss
    # record, and LP-trend sparkline, all of which are fine starting from
    # "no data yet" and filling in as new games happen.
    queue_id: Mapped[int | None] = mapped_column(nullable=True)
    champion: Mapped[str | None] = mapped_column(nullable=True)
    kills: Mapped[int | None] = mapped_column(nullable=True)
    deaths: Mapped[int | None] = mapped_column(nullable=True)
    assists: Mapped[int | None] = mapped_column(nullable=True)
    # This player's league points for this match's queue, as of right after
    # this match (i.e. the same fresh fetch _update_rank_tracking already
    # does) -- the raw values a per-queue LP-trend sparkline plots.
    lp_after: Mapped[int | None] = mapped_column(nullable=True)
    # Set iff this match was a counted loss that got a task assigned --
    # lets the match-history feed show "here's the task this game
    # triggered" without guessing from descriptions/timestamps.
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)


class PityHistory(Base):
    """Append-only log of a user's pity value after each counted win/loss
    (bot/severity.py's apply_loss_pity/apply_win_pity) -- users.pity only
    ever holds the current value, so this is what a pity-over-time chart
    reads from. Never mutated or deleted, only inserted."""

    __tablename__ = "pity_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    pity: Mapped[float] = mapped_column()
    recorded_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


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
    # Severity tier drawn when this task was assigned ("low"/"medium"/
    # "high") -- persisted (mirroring task_templates.tier) so tasks can be
    # sorted by severity, not just chosen by it. A task assigned to a
    # non-opted-in user, or predating this column, is "low" (see
    # init_db()'s backfill below), matching the rest of the app's "no tier
    # = behaves like Low" convention.
    tier: Mapped[str | None] = mapped_column(nullable=True)


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    description: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # Severity tier this task is tagged for ("low"/"medium"/"high") -- new
    # rows always get one (main.py defaults to "low"), and init_db() below
    # backfills any pre-existing NULL rows to "low" too. Still nullable at
    # the schema level since that backfill runs at startup, not atomically
    # with column creation.
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
        # severity_mode is unused now -- tier tagging itself is the opt-in
        # (see severity.has_opted_into_severity) -- but the column is left
        # in place rather than dropped; SQLite DROP COLUMN support is new
        # enough that it's not worth the risk for an unused, harmless column.
        await _add_column_if_missing(conn, "users", "severity_mode", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "task_templates", "tier", "VARCHAR")
        await _add_column_if_missing(conn, "tasks", "tier", "VARCHAR")
        # One-time backfills: rows added before tiers existed, or added
        # without specifying one, default to "low". Idempotent -- a no-op
        # once no NULL rows remain.
        await conn.execute(text("UPDATE task_templates SET tier = 'low' WHERE tier IS NULL"))
        await conn.execute(text("UPDATE tasks SET tier = 'low' WHERE tier IS NULL"))
        await _add_column_if_missing(conn, "processed_matches", "queue_id", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "champion", "VARCHAR")
        await _add_column_if_missing(conn, "processed_matches", "kills", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "deaths", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "assists", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "lp_after", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "task_id", "INTEGER")
        # No backfill for any of the above -- see ProcessedMatch's docstring.
        # pity_history is a brand new table; create_all already made it.


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
