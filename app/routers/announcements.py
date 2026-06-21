from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from typing import Optional, List
from database import get_session
from models import Announcement, AnnouncementCategory, User
from auth_utils import get_current_user, require_sindico
import asyncio

router = APIRouter(prefix="/condos/{condo_id}/announcements")


class AnnouncementCreate(BaseModel):
    title: str
    content: str
    category: AnnouncementCategory = AnnouncementCategory.aviso
    pinned: bool = False


@router.get("", response_model=List[dict])
async def list_announcements(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if user.condo_id != condo_id and user.role != "superadmin":
        raise HTTPException(status_code=403)
    result = await db.exec(
        select(Announcement).where(Announcement.condo_id == condo_id).order_by(Announcement.pinned.desc(), Announcement.created_at.desc())
    )
    items = result.all()
    return [
        {
            "id": a.id, "title": a.title, "content": a.content,
            "category": a.category, "pinned": a.pinned,
            "author_name": a.author_name, "created_at": a.created_at.isoformat(),
            "condo_id": a.condo_id,
        }
        for a in items
    ]


@router.post("")
async def create_announcement(
    condo_id: int,
    data: AnnouncementCreate,
    user: User = Depends(require_sindico),
    db: AsyncSession = Depends(get_session),
):
    if user.condo_id != condo_id and user.role != "superadmin":
        raise HTTPException(status_code=403)
    ann = Announcement(**data.model_dump(), condo_id=condo_id, author_id=user.id, author_name=user.name)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)

    # Enviar push notification para todos os moradores do condomínio
    asyncio.create_task(_notify_residents(condo_id, ann.title, db))

    return {"id": ann.id, "title": ann.title, "category": ann.category, "pinned": ann.pinned}


@router.put("/{ann_id}")
async def update_announcement(
    condo_id: int, ann_id: int, data: AnnouncementCreate,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    ann = await db.get(Announcement, ann_id)
    if not ann or ann.condo_id != condo_id:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump().items():
        setattr(ann, k, v)
    db.add(ann)
    await db.commit()
    return {"id": ann.id, "title": ann.title}


@router.delete("/{ann_id}")
async def delete_announcement(
    condo_id: int, ann_id: int,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    ann = await db.get(Announcement, ann_id)
    if not ann or ann.condo_id != condo_id:
        raise HTTPException(status_code=404)
    await db.delete(ann)
    await db.commit()
    return {"status": "ok"}


async def _notify_residents(condo_id: int, title: str, db: AsyncSession):
    """Envia push para todos os moradores do condomínio."""
    try:
        from services.push import send_push_to_condo
        await send_push_to_condo(condo_id, f"📋 {title}", "Novo aviso publicado", db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Push notification erro: {e}")
