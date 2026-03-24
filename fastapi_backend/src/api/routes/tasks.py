from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db_session
from src.core.deps import get_current_user
from src.models.models import AppUser, Reminder, Tag, Task, TaskAttachment, TaskNote, TaskTag
from src.realtime.manager import manager
from src.schemas.task import (
    ReminderCreate,
    ReminderOut,
    ReminderUpdate,
    TagOut,
    TaskAttachmentCreate,
    TaskAttachmentOut,
    TaskCreate,
    TaskNoteCreate,
    TaskNoteOut,
    TaskOut,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _task_to_out(task: Task, tags: list[Tag]) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        due_at=task.due_at,
        completed_at=task.completed_at,
        sort_order=task.sort_order,
        is_archived=task.is_archived,
        is_recurring=task.is_recurring,
        recurrence_rule=task.recurrence_rule,
        recurrence_interval_days=task.recurrence_interval_days,
        recurrence_end_date=task.recurrence_end_date,
        next_occurrence_at=task.next_occurrence_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        tags=[TagOut.model_validate(t, from_attributes=True) for t in tags],
    )


async def _load_task_or_404(session: AsyncSession, task_id: UUID, owner_id: UUID) -> Task:
    task = (await session.execute(select(Task).where(Task.id == task_id, Task.owner_user_id == owner_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def _replace_task_tags(session: AsyncSession, task: Task, owner_id: UUID, tag_ids: list[UUID]) -> list[Tag]:
    # validate tags belong to user
    if tag_ids:
        tags = (await session.execute(select(Tag).where(Tag.owner_user_id == owner_id, Tag.id.in_(tag_ids)))).scalars().all()
        if len(tags) != len(set(tag_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more tags not found")
    else:
        tags = []

    # delete existing links
    existing = (await session.execute(select(TaskTag).where(TaskTag.task_id == task.id))).scalars().all()
    for link in existing:
        await session.delete(link)

    for t in tags:
        session.add(TaskTag(task_id=task.id, tag_id=t.id))
    return tags


@router.get(
    "",
    response_model=list[TaskOut],
    summary="List tasks",
    description=(
        "List tasks for the current user with search/filter/sort.\n\n"
        "Supported query params:\n"
        "- q: full-text search (title/description)\n"
        "- status: todo/in_progress/done\n"
        "- priority: low/medium/high/urgent\n"
        "- due_from/due_to: filter by due_date range\n"
        "- tag_id: tasks having a given tag\n"
        "- archived: include archived tasks (default false)\n"
        "- sort: created_at|updated_at|due_date|priority|sort_order (default updated_at)\n"
        "- order: asc|desc (default desc)\n"
    ),
)
async def list_tasks(
    q: str | None = Query(None, description="Search query."),
    status_filter: Literal["todo", "in_progress", "done"] | None = Query(None, alias="status", description="Task status."),
    priority: Literal["low", "medium", "high", "urgent"] | None = Query(None, description="Task priority."),
    due_from: date | None = Query(None, description="Due date from (inclusive)."),
    due_to: date | None = Query(None, description="Due date to (inclusive)."),
    tag_id: UUID | None = Query(None, description="Filter to tasks that have this tag."),
    archived: bool = Query(False, description="Include archived tasks."),
    sort: Literal["created_at", "updated_at", "due_date", "priority", "sort_order"] = Query("updated_at", description="Sort field."),
    order: Literal["asc", "desc"] = Query("desc", description="Sort order."),
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> list[TaskOut]:
    filters = [Task.owner_user_id == current_user.id, Task.deleted_at.is_(None)]
    if not archived:
        filters.append(Task.is_archived.is_(False))
    if status_filter:
        filters.append(Task.status == status_filter)
    if priority:
        filters.append(Task.priority == priority)
    if due_from:
        filters.append(Task.due_date >= due_from)
    if due_to:
        filters.append(Task.due_date <= due_to)

    stmt = select(Task).where(and_(*filters))

    if q:
        # matches the idx_task_fts created by DB container
        stmt = stmt.where(
            func.to_tsvector("english", func.coalesce(Task.title, "") + " " + func.coalesce(Task.description, "")).op("@@")(
                func.plainto_tsquery("english", q)
            )
        )

    if tag_id:
        stmt = stmt.join(TaskTag, TaskTag.task_id == Task.id).where(TaskTag.tag_id == tag_id)

    sort_col = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "sort_order": Task.sort_order,
    }[sort]
    stmt = stmt.order_by(sort_col.asc() if order == "asc" else desc(sort_col))

    tasks = (await session.execute(stmt)).scalars().all()

    # bulk load tags
    if not tasks:
        return []
    task_ids = [t.id for t in tasks]
    tag_rows = (
        await session.execute(
            select(TaskTag.task_id, Tag)
            .join(Tag, Tag.id == TaskTag.tag_id)
            .where(TaskTag.task_id.in_(task_ids))
        )
    ).all()

    tags_by_task: dict[UUID, list[Tag]] = {tid: [] for tid in task_ids}
    for tid, tag in tag_rows:
        tags_by_task.setdefault(tid, []).append(tag)

    return [_task_to_out(t, tags_by_task.get(t.id, [])) for t in tasks]


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create task",
    description="Create a new task with optional tag assignment and recurrence fields.",
)
async def create_task(
    req: TaskCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TaskOut:
    task = Task(
        owner_user_id=current_user.id,
        title=req.title,
        description=req.description,
        status=req.status,
        priority=req.priority,
        due_date=req.due_date,
        due_at=req.due_at,
        sort_order=req.sort_order,
        is_recurring=req.is_recurring,
        recurrence_rule=req.recurrence_rule,
        recurrence_interval_days=req.recurrence_interval_days,
        recurrence_end_date=req.recurrence_end_date,
        next_occurrence_at=req.next_occurrence_at,
    )
    session.add(task)
    await session.flush()  # allocate ID

    tags = await _replace_task_tags(session, task, current_user.id, req.tag_ids)

    await session.commit()
    await session.refresh(task)

    out = _task_to_out(task, tags)
    await manager.broadcast_to_user(current_user.id, "task.created", out.model_dump())
    return out


@router.get(
    "/{task_id}",
    response_model=TaskOut,
    summary="Get task",
    description="Fetch a single task including its tags.",
)
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TaskOut:
    task = await _load_task_or_404(session, task_id, current_user.id)
    tags = (
        await session.execute(
            select(Tag).join(TaskTag, TaskTag.tag_id == Tag.id).where(TaskTag.task_id == task.id)
        )
    ).scalars().all()
    return _task_to_out(task, tags)


@router.patch(
    "/{task_id}",
    response_model=TaskOut,
    summary="Update task",
    description="Update fields on a task. If tag_ids is provided, tags are replaced.",
)
async def update_task(
    task_id: UUID,
    req: TaskUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TaskOut:
    task = await _load_task_or_404(session, task_id, current_user.id)

    for field in [
        "title",
        "description",
        "status",
        "priority",
        "due_date",
        "due_at",
        "completed_at",
        "sort_order",
        "is_archived",
        "is_recurring",
        "recurrence_rule",
        "recurrence_interval_days",
        "recurrence_end_date",
        "next_occurrence_at",
    ]:
        val = getattr(req, field)
        if val is not None:
            setattr(task, field, val)

    tags: list[Tag]
    if req.tag_ids is not None:
        tags = await _replace_task_tags(session, task, current_user.id, req.tag_ids)
    else:
        tags = (
            await session.execute(
                select(Tag).join(TaskTag, TaskTag.tag_id == Tag.id).where(TaskTag.task_id == task.id)
            )
        ).scalars().all()

    await session.commit()
    await session.refresh(task)

    out = _task_to_out(task, tags)
    await manager.broadcast_to_user(current_user.id, "task.updated", out.model_dump())
    return out


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete task",
    description="Soft delete a task by setting deleted_at timestamp.",
)
async def delete_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    task = await _load_task_or_404(session, task_id, current_user.id)
    task.deleted_at = datetime.utcnow()
    await session.commit()
    await manager.broadcast_to_user(current_user.id, "task.deleted", {"id": str(task_id)})
    return None


# ---------------- Notes ----------------

@router.get(
    "/{task_id}/notes",
    response_model=list[TaskNoteOut],
    summary="List notes for a task",
    description="Returns notes for a task owned by the current user.",
)
async def list_notes(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> list[TaskNoteOut]:
    await _load_task_or_404(session, task_id, current_user.id)
    notes = (
        await session.execute(
            select(TaskNote).where(TaskNote.task_id == task_id).order_by(TaskNote.created_at.asc())
        )
    ).scalars().all()
    return [TaskNoteOut.model_validate(n, from_attributes=True) for n in notes]


@router.post(
    "/{task_id}/notes",
    response_model=TaskNoteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create note",
    description="Create a note on a task.",
)
async def create_note(
    task_id: UUID,
    req: TaskNoteCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TaskNoteOut:
    await _load_task_or_404(session, task_id, current_user.id)
    note = TaskNote(task_id=task_id, author_user_id=current_user.id, body=req.body)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    out = TaskNoteOut.model_validate(note, from_attributes=True)
    await manager.broadcast_to_user(current_user.id, "task.note.created", out.model_dump())
    return out


@router.delete(
    "/{task_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
    description="Delete a note from a task.",
)
async def delete_note(
    task_id: UUID,
    note_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    await _load_task_or_404(session, task_id, current_user.id)
    note = (await session.execute(select(TaskNote).where(TaskNote.id == note_id, TaskNote.task_id == task_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    await session.delete(note)
    await session.commit()
    await manager.broadcast_to_user(current_user.id, "task.note.deleted", {"id": str(note_id), "task_id": str(task_id)})
    return None


# ---------------- Attachments (metadata only) ----------------

@router.get(
    "/{task_id}/attachments",
    response_model=list[TaskAttachmentOut],
    summary="List attachments",
    description="List attachment metadata for a task.",
)
async def list_attachments(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> list[TaskAttachmentOut]:
    await _load_task_or_404(session, task_id, current_user.id)
    rows = (
        await session.execute(
            select(TaskAttachment).where(TaskAttachment.task_id == task_id).order_by(TaskAttachment.created_at.asc())
        )
    ).scalars().all()
    return [TaskAttachmentOut.model_validate(a, from_attributes=True) for a in rows]


@router.post(
    "/{task_id}/attachments",
    response_model=TaskAttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create attachment metadata",
    description="Create attachment metadata entry. (Actual file upload/storage handled by frontend/storage layer.)",
)
async def create_attachment(
    task_id: UUID,
    req: TaskAttachmentCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TaskAttachmentOut:
    await _load_task_or_404(session, task_id, current_user.id)
    attachment = TaskAttachment(
        task_id=task_id,
        uploader_user_id=current_user.id,
        file_name=req.file_name,
        content_type=req.content_type,
        size_bytes=req.size_bytes,
        storage_key=req.storage_key,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    out = TaskAttachmentOut.model_validate(attachment, from_attributes=True)
    await manager.broadcast_to_user(current_user.id, "task.attachment.created", out.model_dump())
    return out


@router.delete(
    "/{task_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete attachment metadata",
    description="Delete attachment metadata entry.",
)
async def delete_attachment(
    task_id: UUID,
    attachment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    await _load_task_or_404(session, task_id, current_user.id)
    att = (
        await session.execute(
            select(TaskAttachment).where(TaskAttachment.id == attachment_id, TaskAttachment.task_id == task_id)
        )
    ).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    await session.delete(att)
    await session.commit()
    await manager.broadcast_to_user(
        current_user.id, "task.attachment.deleted", {"id": str(attachment_id), "task_id": str(task_id)}
    )
    return None


# ---------------- Reminders ----------------

@router.get(
    "/{task_id}/reminders",
    response_model=list[ReminderOut],
    summary="List reminders",
    description="List reminders for a task.",
)
async def list_reminders(
    task_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> list[ReminderOut]:
    await _load_task_or_404(session, task_id, current_user.id)
    rows = (
        await session.execute(
            select(Reminder).where(Reminder.task_id == task_id, Reminder.user_id == current_user.id).order_by(Reminder.remind_at.asc())
        )
    ).scalars().all()
    return [ReminderOut.model_validate(r, from_attributes=True) for r in rows]


@router.post(
    "/{task_id}/reminders",
    response_model=ReminderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create reminder",
    description="Create an in-app (or email) reminder for a task.",
)
async def create_reminder(
    task_id: UUID,
    req: ReminderCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> ReminderOut:
    await _load_task_or_404(session, task_id, current_user.id)
    reminder = Reminder(
        task_id=task_id,
        user_id=current_user.id,
        remind_at=req.remind_at,
        channel=req.channel,
        status="scheduled",
    )
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    out = ReminderOut.model_validate(reminder, from_attributes=True)
    await manager.broadcast_to_user(current_user.id, "task.reminder.created", out.model_dump())
    return out


@router.patch(
    "/{task_id}/reminders/{reminder_id}",
    response_model=ReminderOut,
    summary="Update reminder",
    description="Update a reminder (time/channel/status).",
)
async def update_reminder(
    task_id: UUID,
    reminder_id: UUID,
    req: ReminderUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> ReminderOut:
    await _load_task_or_404(session, task_id, current_user.id)
    reminder = (
        await session.execute(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.task_id == task_id, Reminder.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    for field in ["remind_at", "channel", "status"]:
        val = getattr(req, field)
        if val is not None:
            setattr(reminder, field, val)

    await session.commit()
    await session.refresh(reminder)
    out = ReminderOut.model_validate(reminder, from_attributes=True)
    await manager.broadcast_to_user(current_user.id, "task.reminder.updated", out.model_dump())
    return out


@router.delete(
    "/{task_id}/reminders/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete reminder",
    description="Delete a reminder.",
)
async def delete_reminder(
    task_id: UUID,
    reminder_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    await _load_task_or_404(session, task_id, current_user.id)
    reminder = (
        await session.execute(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.task_id == task_id, Reminder.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    await session.delete(reminder)
    await session.commit()
    await manager.broadcast_to_user(
        current_user.id, "task.reminder.deleted", {"id": str(reminder_id), "task_id": str(task_id)}
    )
    return None
