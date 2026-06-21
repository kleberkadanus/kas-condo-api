from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from database import get_session
from models import PushToken, User
from auth_utils import get_current_user

router = APIRouter(prefix="/notifications")


class RegisterTokenRequest(BaseModel):
    token: str
    platform: str = "android"


@router.post("/register")
async def register_token(
    data: RegisterTokenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    # Evita duplicata
    existing = await db.exec(select(PushToken).where(PushToken.token == data.token))
    if not existing.first():
        pt = PushToken(user_id=user.id, token=data.token, platform=data.platform)
        db.add(pt)
        await db.commit()
    return {"status": "ok"}
