import httpx
import logging
import os
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from models import PushToken, User

logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
FCM_URL = "https://fcm.googleapis.com/fcm/send"
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")


async def send_push(token: str, title: str, body: str, data: dict = {}):
    if token.startswith("ExponentPushToken"):
        await _send_expo(token, title, body, data)
    elif token and FCM_SERVER_KEY:
        await _send_fcm(token, title, body, data)
    else:
        logger.warning(f"[Push] Token ignorado (sem FCM_SERVER_KEY ou token inválido): {token[:20]}...")


async def _send_expo(token: str, title: str, body: str, data: dict):
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
            logger.warning(f"[Push] Expo falhou: {resp.text}")


async def _send_fcm(token: str, title: str, body: str, data: dict):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            FCM_URL,
            headers={
                "Authorization": f"key={FCM_SERVER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "to": token,
                "notification": {"title": title, "body": body, "sound": "default"},
                "data": data,
                "priority": "high",
            },
        )
        if resp.status_code != 200:
            logger.warning(f"[Push] FCM falhou: {resp.text}")


async def send_push_to_condo(condo_id: int, title: str, body: str, db: AsyncSession, data: dict = {}):
    users = await db.exec(select(User).where(User.condo_id == condo_id, User.active == True))
    user_ids = [u.id for u in users.all()]
    if not user_ids:
        return
    tokens = await db.exec(select(PushToken).where(PushToken.user_id.in_(user_ids)))
    for pt in tokens.all():
        try:
            await send_push(pt.token, title, body, data)
        except Exception as e:
            logger.error(f"[Push] Erro para token {pt.token[:20]}: {e}")


async def send_push_to_user(user_id: int, title: str, body: str, db: AsyncSession, data: dict = {}):
    tokens = await db.exec(select(PushToken).where(PushToken.user_id == user_id))
    for pt in tokens.all():
        try:
            await send_push(pt.token, title, body, data)
        except Exception as e:
            logger.error(f"[Push] Erro: {e}")
