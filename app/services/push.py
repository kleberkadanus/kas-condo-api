"""
Serviço de push notifications via Expo Push API.
Não requer Firebase configurado pelo usuário — usa a infraestrutura do Expo.
"""
import httpx
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from models import PushToken, User

logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(token: str, title: str, body: str, data: dict = {}):
    if not token.startswith("ExponentPushToken"):
        return
    async with httpx.AsyncClient() as client:
        resp = await client.post(EXPO_PUSH_URL, json={
            "to": token,
            "title": title,
            "body": body,
            "data": data,
            "sound": "default",
            "priority": "high",
        })
        if resp.status_code != 200:
            logger.warning(f"Push falhou: {resp.text}")


async def send_push_to_condo(condo_id: int, title: str, body: str, db: AsyncSession, data: dict = {}):
    """Envia push para todos os moradores do condomínio."""
    users = await db.exec(select(User).where(User.condo_id == condo_id, User.active == True))
    user_ids = [u.id for u in users.all()]
    if not user_ids:
        return
    tokens = await db.exec(select(PushToken).where(PushToken.user_id.in_(user_ids)))
    for pt in tokens.all():
        try:
            await send_push(pt.token, title, body, data)
        except Exception as e:
            logger.error(f"Push erro para token {pt.token}: {e}")


async def send_push_to_user(user_id: int, title: str, body: str, db: AsyncSession, data: dict = {}):
    """Envia push para um usuário específico."""
    tokens = await db.exec(select(PushToken).where(PushToken.user_id == user_id))
    for pt in tokens.all():
        try:
            await send_push(pt.token, title, body, data)
        except Exception as e:
            logger.error(f"Push erro: {e}")
