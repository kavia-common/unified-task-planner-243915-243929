from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TagOut(BaseModel):
    id: UUID = Field(..., description="Tag ID.")
    name: str = Field(..., description="Tag name.")
    color: str | None = Field(None, description="Optional tag color.")


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="Tag name.")
    color: str | None = Field(None, description="Optional tag color.")


class TagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80, description="Tag name.")
    color: str | None = Field(None, description="Optional tag color.")


class TaskNoteOut(BaseModel):
    id: UUID = Field(..., description="Note ID.")
    task_id: UUID = Field(..., description="Task ID.")
    body: str = Field(..., description="Note body.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


class TaskNoteCreate(BaseModel):
    body: str = Field(..., min_length=1, description="Note body.")


class TaskAttachmentOut(BaseModel):
    id: UUID = Field(..., description="Attachment ID.")
    task_id: UUID = Field(..., description="Task ID.")
    file_name: str = Field(..., description="Original file name.")
    content_type: str | None = Field(None, description="MIME content type.")
    size_bytes: int | None = Field(None, description="File size in bytes.")
    storage_key: str | None = Field(None, description="Storage key/path.")
    created_at: datetime = Field(..., description="Created timestamp.")


class TaskAttachmentCreate(BaseModel):
    file_name: str = Field(..., min_length=1, description="Original file name.")
    content_type: str | None = Field(None, description="MIME content type.")
    size_bytes: int | None = Field(None, ge=0, description="File size in bytes.")
    storage_key: str | None = Field(None, description="Storage key/path.")


class ReminderOut(BaseModel):
    id: UUID = Field(..., description="Reminder ID.")
    task_id: UUID = Field(..., description="Task ID.")
    remind_at: datetime = Field(..., description="When to remind the user.")
    channel: str = Field(..., description="Channel: in_app or email.")
    status: str = Field(..., description="Status: scheduled/sent/cancelled/failed.")
    last_error: str | None = Field(None, description="Last error if failed.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


class ReminderCreate(BaseModel):
    remind_at: datetime = Field(..., description="When to remind the user.")
    channel: str = Field("in_app", description="Channel: in_app or email.")


class ReminderUpdate(BaseModel):
    remind_at: datetime | None = Field(None, description="When to remind the user.")
    channel: str | None = Field(None, description="Channel: in_app or email.")
    status: str | None = Field(None, description="Status: scheduled/sent/cancelled/failed.")


class TaskOut(BaseModel):
    id: UUID = Field(..., description="Task ID.")
    title: str = Field(..., description="Task title.")
    description: str | None = Field(None, description="Task description.")
    status: str = Field(..., description="todo/in_progress/done.")
    priority: str = Field(..., description="low/medium/high/urgent.")
    due_date: date | None = Field(None, description="Due date.")
    due_at: datetime | None = Field(None, description="Due timestamp.")
    completed_at: datetime | None = Field(None, description="Completed timestamp.")
    sort_order: int = Field(..., description="Sort order within a column/list.")
    is_archived: bool = Field(..., description="Archived flag.")
    is_recurring: bool = Field(..., description="Recurring flag.")
    recurrence_rule: str | None = Field(None, description="RRULE text.")
    recurrence_interval_days: int | None = Field(None, description="Simple recurrence interval in days.")
    recurrence_end_date: date | None = Field(None, description="Recurrence end date.")
    next_occurrence_at: datetime | None = Field(None, description="Next occurrence timestamp.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")

    tags: list[TagOut] = Field(default_factory=list, description="Tags attached to this task.")


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task title.")
    description: str | None = Field(None, description="Task description.")
    status: str = Field("todo", description="todo/in_progress/done.")
    priority: str = Field("medium", description="low/medium/high/urgent.")
    due_date: date | None = Field(None, description="Due date.")
    due_at: datetime | None = Field(None, description="Due timestamp.")
    sort_order: int = Field(0, description="Sort order.")

    is_recurring: bool = Field(False, description="Whether the task recurs.")
    recurrence_rule: str | None = Field(None, description="RRULE string.")
    recurrence_interval_days: int | None = Field(None, ge=1, description="Simple interval in days.")
    recurrence_end_date: date | None = Field(None, description="End date for recurrence.")
    next_occurrence_at: datetime | None = Field(None, description="Next occurrence timestamp.")

    tag_ids: list[UUID] = Field(default_factory=list, description="List of tag IDs to assign.")


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200, description="Task title.")
    description: str | None = Field(None, description="Task description.")
    status: str | None = Field(None, description="todo/in_progress/done.")
    priority: str | None = Field(None, description="low/medium/high/urgent.")
    due_date: date | None = Field(None, description="Due date.")
    due_at: datetime | None = Field(None, description="Due timestamp.")
    completed_at: datetime | None = Field(None, description="Completed timestamp.")
    sort_order: int | None = Field(None, description="Sort order.")

    is_archived: bool | None = Field(None, description="Archived flag.")
    is_recurring: bool | None = Field(None, description="Recurring flag.")
    recurrence_rule: str | None = Field(None, description="RRULE string.")
    recurrence_interval_days: int | None = Field(None, ge=1, description="Simple interval in days.")
    recurrence_end_date: date | None = Field(None, description="End date for recurrence.")
    next_occurrence_at: datetime | None = Field(None, description="Next occurrence timestamp.")

    tag_ids: list[UUID] | None = Field(None, description="Replace tags with these tag IDs.")
