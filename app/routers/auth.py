from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from database import get_session
from models import User
from auth_utils import verify_password, create_token, hash_password, get_current_user

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(User).where(User.email == data.email.lower()))
    user = result.first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    if not user.active:
        raise HTTPException(status_code=401, detail="Conta desativada")
    token = create_token(user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "condo_id": user.condo_id,
            "apt_number": user.apt_number,
            "sip_user": user.sip_user,
            "sip_password": user.sip_password,
        },
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "condo_id": user.condo_id,
        "apt_number": user.apt_number,
        "avatar_url": user.avatar_url,
        "sip_user": user.sip_user,
        "sip_password": user.sip_password,
    }


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    user.hashed_password = hash_password(data.new_password)
    db.add(user)
    await db.commit()
    return {"status": "ok"}
