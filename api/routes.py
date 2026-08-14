"""Protected REST endpoints. Every route is scoped to the authenticated
user's own discord_id -- there is no cross-user or admin access here."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from auth import CurrentUser, get_current_user
from bot_bridge import (
    QUEUE_ID_LABELS,
    RANKED_FLEX_QUEUE_ID,
    RANKED_QUEUE_IDS,
    RANKED_SOLO_QUEUE_ID,
    PityHistory,
    ProcessedMatch,
    Task,
    TaskTemplate,
    User,
    async_session,
    complete_task,
    compute_odds,
    current_streak,
    format_rank,
    has_opted_into_severity,
    number_items,
    sort_by_tier_then_date,
    sort_matches_recent_first,
    task_completion_rate,
    tasks_completed_by_day,
    tier_breakdown,
    win_loss_record,
)
from schemas import (
    ActivityPointOut,
    MatchOut,
    MatchTaskOut,
    MeOut,
    PityHistoryPointOut,
    RankQueueOut,
    StatsOverviewOut,
    StatusOut,
    StreakOut,
    TaskOut,
    TaskTemplateCreate,
    TaskTemplateOut,
    TierStatOut,
    WinLossOut,
)

router = APIRouter()

# How many recent games feed a rank's LP-trend sparkline -- a lightweight
# indicator, not a full chart, so this is deliberately small.
LP_TREND_GAMES = 8


def _task_out(number: int, task: Task) -> TaskOut:
    return TaskOut(
        number=number,
        id=task.id,
        match_id=task.match_id,
        task_description=task.task_description,
        status=task.status,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


def _template_out(number: int | None, template: TaskTemplate) -> TaskTemplateOut:
    return TaskTemplateOut(
        number=number,
        id=template.id,
        description=template.description,
        active=template.active,
        tier=template.tier,
        created_at=template.created_at,
    )


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    status: Literal["pending", "all"] = "pending",
    user: CurrentUser = Depends(get_current_user),
):
    async with async_session() as session:
        query = select(Task).where(Task.discord_id == user.discord_id)
        if status == "pending":
            query = query.where(Task.status == "pending")
        query = query.order_by(Task.created_at.desc())
        result = await session.execute(query)
        tasks = result.scalars().all()

        # Pending matches /status's tier-grouped order; history stays
        # most-recent-first, unchanged -- it's a log of what happened, not
        # a worklist to sort by severity.
        if status == "pending":
            tasks = sort_by_tier_then_date(tasks)

        return [_task_out(n, t) for n, t in number_items(tasks)]


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
async def complete_task_route(task_id: int, user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        task = await session.get(Task, task_id)
        if task is None or task.discord_id != user.discord_id:
            raise HTTPException(404, f"No task #{task_id} found for you.")
        if task.status != "pending":
            raise HTTPException(409, f"Task #{task_id} is already marked {task.status}.")

        await complete_task(session, task)
        await session.commit()
        await session.refresh(task)

        # Position within the full history list (same order History shows),
        # since that's the list this task belongs to now that it's done.
        history_result = await session.execute(
            select(Task).where(Task.discord_id == user.discord_id).order_by(Task.created_at.desc())
        )
        number_by_id = {t.id: n for n, t in number_items(history_result.scalars().all())}
        return _task_out(number_by_id[task.id], task)


@router.get("/task-templates", response_model=list[TaskTemplateOut])
async def list_task_templates(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.discord_id == user.discord_id)
            .order_by(TaskTemplate.id)
        )
        # Tier-grouped, same as /mytasks -- applied to the whole list
        # (active + inactive together) so the dashboard's display order
        # matches Discord's for the active ones, rather than active and
        # inactive rows interleaving strictly by creation date.
        templates = sort_by_tier_then_date(result.scalars().all())

        # Only active templates get numbered -- matches /mytasks and
        # /removetask in Discord, which never show or accept a number for
        # an inactive (removed) one.
        number_by_id = {t.id: n for n, t in number_items([t for t in templates if t.active])}
        return [_template_out(number_by_id.get(t.id), t) for t in templates]


@router.post("/task-templates", response_model=TaskTemplateOut, status_code=201)
async def create_task_template(
    body: TaskTemplateCreate, user: CurrentUser = Depends(get_current_user)
):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)
        if db_user is None:
            raise HTTPException(400, "Register with /register in Discord before adding tasks.")

        template = TaskTemplate(
            discord_id=user.discord_id, description=body.description, tier=body.tier
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)

        active_result = await session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.discord_id == user.discord_id, TaskTemplate.active.is_(True))
            .order_by(TaskTemplate.id)
        )
        active_templates = sort_by_tier_then_date(active_result.scalars().all())
        number_by_id = {t.id: n for n, t in number_items(active_templates)}
        return _template_out(number_by_id[template.id], template)


@router.delete("/task-templates/{template_id}", status_code=204)
async def delete_task_template(template_id: int, user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        template = await session.get(TaskTemplate, template_id)
        if template is None or template.discord_id != user.discord_id:
            raise HTTPException(404, f"No task template #{template_id} found for you.")

        template.active = False
        await session.commit()


@router.get("/status", response_model=StatusOut)
async def get_status(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)
        pity = db_user.pity if db_user is not None else 0.0
        opted_in = await has_opted_into_severity(session, user.discord_id)

        result = await session.execute(
            select(Task).where(Task.discord_id == user.discord_id, Task.status == "pending")
        )
        pending_count = len(result.scalars().all())

    return StatusOut(
        pending_count=pending_count,
        opted_into_severity=opted_in,
        pity=pity,
        odds=compute_odds(pity),
    )


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)

    return MeOut(
        discord_id=user.discord_id,
        discord_username=user.username,
        riot_game_name=db_user.riot_game_name if db_user else None,
        riot_tag_line=db_user.riot_tag_line if db_user else None,
        registered_at=db_user.registered_at if db_user else None,
        muted=db_user.muted if db_user else False,
    )


def _lp_trend(ranked_matches: list[ProcessedMatch], queue_id: int) -> list[int]:
    """Oldest-first lp_after values for the given queue, capped to
    LP_TREND_GAMES -- a sparkline data source. Matches with no captured
    lp_after (pre-migration, or the rank fetch failed that game) are
    skipped rather than shown as gaps."""
    queue_matches = sort_matches_recent_first(
        [m for m in ranked_matches if m.queue_id == queue_id and m.lp_after is not None]
    )
    return [m.lp_after for m in reversed(queue_matches[:LP_TREND_GAMES])]


def _rank_out(db_user: User | None, queue: str, trend: list[int]) -> RankQueueOut | None:
    tier = (db_user.solo_tier if queue == "solo" else db_user.flex_tier) if db_user else None
    if tier is None:
        return None  # not ranked in this queue yet -- nothing to show

    rank = db_user.solo_rank if queue == "solo" else db_user.flex_rank
    lp = db_user.solo_lp if queue == "solo" else db_user.flex_lp
    entry = {"tier": tier, "rank": rank, "leaguePoints": lp}
    return RankQueueOut(tier=tier, rank=rank, lp=lp, formatted=format_rank(entry), trend=trend)


@router.get("/stats/overview", response_model=StatsOverviewOut)
async def get_stats_overview(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)

        ranked_result = await session.execute(
            select(ProcessedMatch).where(
                ProcessedMatch.discord_id == user.discord_id,
                ProcessedMatch.queue_id.in_(RANKED_QUEUE_IDS),
            )
        )
        ranked_matches = ranked_result.scalars().all()
        solo_matches = [m for m in ranked_matches if m.queue_id == RANKED_SOLO_QUEUE_ID]
        flex_matches = [m for m in ranked_matches if m.queue_id == RANKED_FLEX_QUEUE_ID]

        direction, count = current_streak(sort_matches_recent_first(ranked_matches))

        tasks_result = await session.execute(select(Task).where(Task.discord_id == user.discord_id))
        all_tasks = tasks_result.scalars().all()

    return StatsOverviewOut(
        solo_rank=_rank_out(db_user, "solo", _lp_trend(ranked_matches, RANKED_SOLO_QUEUE_ID)),
        flex_rank=_rank_out(db_user, "flex", _lp_trend(ranked_matches, RANKED_FLEX_QUEUE_ID)),
        win_loss_overall=WinLossOut(**win_loss_record(ranked_matches)),
        win_loss_solo=WinLossOut(**win_loss_record(solo_matches)),
        win_loss_flex=WinLossOut(**win_loss_record(flex_matches)),
        streak=StreakOut(direction=direction, count=count),
        task_completion_rate=task_completion_rate(all_tasks),
        tier_breakdown={tier: TierStatOut(**stat) for tier, stat in tier_breakdown(all_tasks).items()},
        activity=[ActivityPointOut(**point) for point in tasks_completed_by_day(all_tasks)],
    )


@router.get("/matches", response_model=list[MatchOut])
async def list_matches(limit: int = 10, user: CurrentUser = Depends(get_current_user)):
    limit = max(1, min(limit, 50))

    async with async_session() as session:
        result = await session.execute(
            select(ProcessedMatch).where(
                ProcessedMatch.discord_id == user.discord_id,
                ProcessedMatch.queue_id.in_(RANKED_QUEUE_IDS),
            )
        )
        matches = sort_matches_recent_first(result.scalars().all())[:limit]

        task_ids = [m.task_id for m in matches if m.task_id is not None]
        tasks_by_id = {}
        if task_ids:
            tasks_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
            tasks_by_id = {t.id: t for t in tasks_result.scalars().all()}

        return [
            MatchOut(
                match_id=m.match_id,
                queue=QUEUE_ID_LABELS.get(m.queue_id, "Ranked"),
                was_loss=m.was_loss,
                champion=m.champion,
                kills=m.kills,
                deaths=m.deaths,
                assists=m.assists,
                detected_at=m.detected_at,
                task=(
                    MatchTaskOut(
                        id=tasks_by_id[m.task_id].id,
                        task_description=tasks_by_id[m.task_id].task_description,
                        status=tasks_by_id[m.task_id].status,
                    )
                    if m.task_id in tasks_by_id
                    else None
                ),
            )
            for m in matches
        ]


@router.get("/pity-history", response_model=list[PityHistoryPointOut])
async def list_pity_history(limit: int = 50, user: CurrentUser = Depends(get_current_user)):
    limit = max(1, min(limit, 200))

    async with async_session() as session:
        result = await session.execute(
            select(PityHistory)
            .where(PityHistory.discord_id == user.discord_id)
            .order_by(PityHistory.recorded_at.desc())
            .limit(limit)
        )
        points = list(reversed(result.scalars().all()))  # oldest first, for a left-to-right chart
        return [PityHistoryPointOut(pity=p.pity, recorded_at=p.recorded_at) for p in points]
