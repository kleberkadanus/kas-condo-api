from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from typing import Optional
from database import get_session, engine
from models import Message, User, UserRole
from auth_utils import get_current_user
import asyncio

router = APIRouter()
chat_router = APIRouter(prefix="/condos/{condo_id}/chat")


@chat_router.get("")
async def list_messages(
    condo_id: int,
    limit: int = 60,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    if user.condo_id != condo_id and user.role.value not in ("superadmin", "sindico", "zelador"):
        raise HTTPException(status_code=403)
    result = await db.exec(
        select(Message)
        .where(Message.condo_id == condo_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    msgs = result.all()
    return [
        {
            "id": m.id,
            "content": m.content,
            "sender_id": m.sender_id,
            "sender_name": m.sender_name,
            "sender_role": m.sender_role,
            "created_at": m.created_at.isoformat(),
            "read_at": m.read_at.isoformat() if m.read_at else None,
            "mine": m.sender_id == user.id,
        }
        for m in reversed(msgs)
    ]


@chat_router.post("")
async def send_message(
    condo_id: int,
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    content = (data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="Mensagem nao pode ser vazia")
    if user.condo_id != condo_id and user.role.value not in ("superadmin", "sindico", "zelador"):
        raise HTTPException(status_code=403)
    msg = Message(
        condo_id=condo_id,
        sender_id=user.id,
        sender_name=user.name,
        sender_role=user.role.value if hasattr(user.role, "value") else str(user.role),
        content=content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    sender_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    sender_name = user.name
    msg_id = msg.id

    asyncio.create_task(_notify_chat(condo_id, sender_name, sender_role, content))

    return {
        "id": msg_id,
        "content": msg.content,
        "sender_id": msg.sender_id,
        "sender_name": msg.sender_name,
        "sender_role": msg.sender_role,
        "created_at": msg.created_at.isoformat(),
        "mine": True,
    }


@chat_router.put("/read")
async def mark_read(
    condo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await db.exec(
        select(Message)
        .where(Message.condo_id == condo_id, Message.read_at == None, Message.sender_id != user.id)
    )
    now = datetime.utcnow()
    for m in result.all():
        m.read_at = now
        db.add(m)
    await db.commit()
    return {"ok": True}


async def _notify_chat(condo_id: int, sender_name: str, sender_role: str, content: str):
    """Envia push para o destinatario correto: morador -> sindico, sindico -> moradores."""
    try:
        from services.push import send_push_to_user, send_push_to_condo
        async with AsyncSession(engine) as db:
            if sender_role in ("morador", "proprietario"):
                # Notifica sindicos do condo
                sindicos = await db.exec(
                    select(User).where(User.condo_id == condo_id, User.role == UserRole.sindico, User.active == True)
                )
                for sindico in sindicos.all():
                    await send_push_to_user(sindico.id, f"Chat - {sender_name}", content[:100], db)
            else:
                # Sindico/zelador -> notifica moradores
                moradores = await db.exec(
                    select(User).where(User.condo_id == condo_id, User.role == UserRole.morador, User.active == True)
                )
                for morador in moradores.all():
                    await send_push_to_user(morador.id, f"Chat - Sindico", content[:100], db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Push chat erro: {e}")


router.include_router(chat_router)
