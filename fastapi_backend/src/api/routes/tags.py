from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db_session
from src.core.deps import get_current_user
from src.models.models import AppUser, Tag
from src.schemas.task import TagCreate, TagOut, TagUpdate

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get(
    "",
    response_model=list[TagOut],
    summary="List tags",
    description="List all tags for the current user.",
)
async def list_tags(
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> list[TagOut]:
    rows = (await session.execute(select(Tag).where(Tag.owner_user_id == current_user.id).order_by(Tag.name.asc()))).scalars().all()
    return [TagOut.model_validate(t, from_attributes=True) for t in rows]


@router.post(
    "",
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag for the current user.",
)
async def create_tag(
    req: TagCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TagOut:
    existing = (
        await session.execute(
            select(Tag).where(Tag.owner_user_id == current_user.id, Tag.name == req.name)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")

    tag = Tag(owner_user_id=current_user.id, name=req.name, color=req.color)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return TagOut.model_validate(tag, from_attributes=True)


@router.patch(
    "/{tag_id}",
    response_model=TagOut,
    summary="Update tag",
    description="Update tag name/color.",
)
async def update_tag(
    tag_id: UUID,
    req: TagUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> TagOut:
    tag = (
        await session.execute(select(Tag).where(Tag.id == tag_id, Tag.owner_user_id == current_user.id))
    ).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if req.name is not None:
        tag.name = req.name
    if req.color is not None:
        tag.color = req.color

    await session.commit()
    await session.refresh(tag)
    return TagOut.model_validate(tag, from_attributes=True)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag. Task associations are removed by cascade.",
)
async def delete_tag(
    tag_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    tag = (
        await session.execute(select(Tag).where(Tag.id == tag_id, Tag.owner_user_id == current_user.id))
    ).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    await session.delete(tag)
    await session.commit()
    return None
