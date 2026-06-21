from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from typing import Optional, List
from database import get_session
from models import Apartment, ParkingSlot, Camera, User
from auth_utils import get_current_user, require_sindico

router = APIRouter()


# ─── Apartamentos ──────────────────────────────────────────────────

apt_router = APIRouter(prefix="/condos/{condo_id}/apartments")


@apt_router.get("", response_model=List[dict])
async def list_apartments(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Apartment).where(Apartment.condo_id == condo_id).order_by(Apartment.number))
    apts = result.all()
    out = []
    for a in apts:
        slots = await db.exec(select(ParkingSlot).where(ParkingSlot.apt_id == a.id))
        out.append({
            "id": a.id, "number": a.number, "block": a.block, "floor": a.floor,
            "condo_id": a.condo_id, "owner_id": a.owner_id,
            "parking_slots": [{"id": s.id, "number": s.number, "type": s.type} for s in slots.all()],
        })
    return out


class ApartmentCreate(BaseModel):
    number: str
    block: Optional[str] = None
    floor: Optional[int] = None
    owner_id: Optional[int] = None


@apt_router.post("")
async def create_apartment(condo_id: int, data: ApartmentCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    apt = Apartment(**data.model_dump(), condo_id=condo_id)
    db.add(apt)
    await db.commit()
    await db.refresh(apt)
    return {"id": apt.id, "number": apt.number}


# ─── Vagas ────────────────────────────────────────────────────────

parking_router = APIRouter(prefix="/condos/{condo_id}/parking")


@parking_router.get("", response_model=List[dict])
async def list_parking(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(ParkingSlot).where(ParkingSlot.condo_id == condo_id).order_by(ParkingSlot.number))
    return [{"id": s.id, "number": s.number, "type": s.type, "apt_id": s.apt_id} for s in result.all()]


# ─── Câmeras ─────────────────────────────────────────────────────

camera_router = APIRouter(prefix="/condos/{condo_id}/cameras")


@camera_router.get("", response_model=List[dict])
async def list_cameras(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Camera).where(Camera.condo_id == condo_id))
    return [{"id": c.id, "name": c.name, "location": c.location, "hls_url": c.hls_url, "active": c.active} for c in result.all()]


# ─── Moradores ────────────────────────────────────────────────────

resident_router = APIRouter(prefix="/condos/{condo_id}/residents")


@resident_router.get("", response_model=List[dict])
async def list_residents(condo_id: int, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(User).where(User.condo_id == condo_id, User.role == "morador").order_by(User.name))
    return [
        {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone,
         "apt_number": u.apt_number, "condo_id": u.condo_id, "active": u.active,
         "sip_extension": u.sip_user}
        for u in result.all()
    ]


class ResidentCreate(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    apt_number: str
    sip_extension: Optional[str] = None


@resident_router.post("")
async def create_resident(condo_id: int, data: ResidentCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    from auth_utils import hash_password
    existing = await db.exec(select(User).where(User.email == data.email.lower()))
    if existing.first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    new_user = User(
        name=data.name,
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role="morador",
        condo_id=condo_id,
        apt_number=data.apt_number,
        phone=data.phone,
        sip_user=data.sip_extension,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"id": new_user.id, "name": new_user.name, "apt_number": new_user.apt_number}


@resident_router.put("/{resident_id}")
async def update_resident(condo_id: int, resident_id: int, data: dict, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    resident = await db.get(User, resident_id)
    if not resident or resident.condo_id != condo_id:
        raise HTTPException(status_code=404)
    for k, v in data.items():
        if hasattr(resident, k) and k not in ["id", "hashed_password"]:
            setattr(resident, k, v)
    db.add(resident)
    await db.commit()
    return {"id": resident.id}


@resident_router.delete("/{resident_id}")
async def delete_resident(condo_id: int, resident_id: int, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    resident = await db.get(User, resident_id)
    if not resident or resident.condo_id != condo_id:
        raise HTTPException(status_code=404)
    resident.active = False
    db.add(resident)
    await db.commit()
    return {"status": "ok"}


router.include_router(apt_router)
router.include_router(parking_router)
router.include_router(camera_router)
router.include_router(resident_router)
