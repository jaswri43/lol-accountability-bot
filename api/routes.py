"""Protected REST endpoints. Every route is scoped to the authenticated
user's own discord_id -- there is no cross-user or admin access here."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from auth import CurrentUser, get_current_user
from bot_bridge import (
    Task,
    TaskTemplate,
    User,
    async_session,
    complete_task,
    compute_odds,
    has_opted_into_severity,
    number_items,
)
from schemas import MeOut, StatusOut, TaskOut, TaskTemplateCreate, TaskTemplateOut

router = APIRouter()


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
        templates = result.scalars().all()

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
        number_by_id = {t.id: n for n, t in number_items(active_result.scalars().all())}
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
