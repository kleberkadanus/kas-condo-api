from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from typing import Optional, List
from database import get_session
from models import Condo, User, UserRole, PlanType
from auth_utils import require_superadmin, hash_password

router = APIRouter(prefix="/admin")


class CondoCreate(BaseModel):
    name: str
    slug: str
    address: str = ""
    city: str = ""
    state: str = "SP"
    plan: PlanType = PlanType.basic
    portaria_extension: str = "9000"
    sip_domain: Optional[str] = None


@router.get("/condos", response_model=List[dict])
async def list_condos(user=Depends(require_superadmin), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Condo).order_by(Condo.name))
    return [
        {
            "id": c.id, "name": c.name, "slug": c.slug, "address": c.address,
            "city": c.city, "state": c.state, "plan": c.plan,
            "active": c.active, "logo_url": c.logo_url,
            "cameras": [], "amenities": [],
        }
        for c in result.all()
    ]


@router.post("/condos")
async def create_condo(data: CondoCreate, user=Depends(require_superadmin), db: AsyncSession = Depends(get_session)):
    existing = await db.exec(select(Condo).where(Condo.slug == data.slug))
    if existing.first():
        raise HTTPException(status_code=409, detail="Slug já em uso")
    condo = Condo(**data.model_dump())
    db.add(condo)
    await db.commit()
    await db.refresh(condo)
    return {"id": condo.id, "name": condo.name, "slug": condo.slug}


@router.put("/condos/{condo_id}")
async def update_condo(condo_id: int, data: dict, user=Depends(require_superadmin), db: AsyncSession = Depends(get_session)):
    condo = await db.get(Condo, condo_id)
    if not condo:
        raise HTTPException(status_code=404)
    for k, v in data.items():
        if hasattr(condo, k) and k not in ["id"]:
            setattr(condo, k, v)
    db.add(condo)
    await db.commit()
    return {"id": condo.id}


@router.delete("/condos/{condo_id}")
async def delete_condo(condo_id: int, user=Depends(require_superadmin), db: AsyncSession = Depends(get_session)):
    condo = await db.get(Condo, condo_id)
    if not condo:
        raise HTTPException(status_code=404)
    condo.active = False
    db.add(condo)
    await db.commit()
    return {"status": "ok"}


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: UserRole = UserRole.morador
    apt_number: Optional[str] = None
    sip_extension: Optional[str] = None


@router.post("/condos/{condo_id}/users")
async def create_user(
    condo_id: int, data: UserCreate,
    user=Depends(require_superadmin),
    db: AsyncSession = Depends(get_session),
):
    existing = await db.exec(select(User).where(User.email == data.email.lower()))
    if existing.first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    new_user = User(
        name=data.name,
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role=data.role,
        condo_id=condo_id,
        apt_number=data.apt_number,
        sip_user=data.sip_extension,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"id": new_user.id, "name": new_user.name, "role": new_user.role}
