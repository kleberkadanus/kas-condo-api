from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from typing import Optional, List
from database import get_session
from models import Apartment, ParkingSlot, Camera, User, Amenity
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
    return [{"id": s.id, "number": s.number, "type": s.type, "apt_id": s.apt_id, "plate": s.plate} for s in result.all()]


class ParkingCreate(BaseModel):
    number: str
    type: str = "covered"
    apt_id: Optional[int] = None
    plate: Optional[str] = None


@parking_router.post("")
async def create_parking(condo_id: int, data: ParkingCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    if data.apt_id is not None:
        apt = await db.get(Apartment, data.apt_id)
        if not apt or apt.condo_id != condo_id:
            raise HTTPException(status_code=422, detail="Apartamento não encontrado neste condomínio")
    slot = ParkingSlot(**data.model_dump(), condo_id=condo_id)
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return {"id": slot.id, "number": slot.number, "type": slot.type, "apt_id": slot.apt_id, "plate": slot.plate}


@parking_router.put("/{slot_id}")
async def update_parking(condo_id: int, slot_id: int, data: ParkingCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    slot = await db.get(ParkingSlot, slot_id)
    if not slot or slot.condo_id != condo_id:
        raise HTTPException(status_code=404)
    if data.apt_id is not None:
        apt = await db.get(Apartment, data.apt_id)
        if not apt or apt.condo_id != condo_id:
            raise HTTPException(status_code=422, detail="Apartamento não encontrado neste condomínio")
    for k, v in data.model_dump().items():
        setattr(slot, k, v)
    db.add(slot)
    await db.commit()
    return {"id": slot.id, "number": slot.number, "type": slot.type, "apt_id": slot.apt_id, "plate": slot.plate}


@parking_router.delete("/{slot_id}")
async def delete_parking(condo_id: int, slot_id: int, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    slot = await db.get(ParkingSlot, slot_id)
    if not slot or slot.condo_id != condo_id:
        raise HTTPException(status_code=404)
    await db.delete(slot)
    await db.commit()
    return {"status": "ok"}


# ─── Câmeras ─────────────────────────────────────────────────────

camera_router = APIRouter(prefix="/condos/{condo_id}/cameras")


def _camera_dict(c: Camera) -> dict:
    return {
        "id": c.id, "name": c.name, "location": c.location,
        "hls_url": c.hls_url, "rtsp_url": getattr(c, "rtsp_url", ""),
        "active": c.active,
    }


@camera_router.get("", response_model=List[dict])
async def list_cameras(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Camera).where(Camera.condo_id == condo_id))
    return [_camera_dict(c) for c in result.all()]


class CameraCreate(BaseModel):
    name: str
    location: str = ""
    hls_url: str = ""
    rtsp_url: str = ""
    active: bool = True


@camera_router.post("")
async def create_camera(condo_id: int, data: CameraCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    cam = Camera(
        name=data.name, location=data.location,
        hls_url=data.hls_url, condo_id=condo_id, active=data.active,
    )
    try:
        cam.rtsp_url = data.rtsp_url
    except Exception:
        pass
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    return _camera_dict(cam)


@camera_router.put("/{cam_id}")
async def update_camera(condo_id: int, cam_id: int, data: CameraCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    cam = await db.get(Camera, cam_id)
    if not cam or cam.condo_id != condo_id:
        raise HTTPException(status_code=404)
    cam.name = data.name
    cam.location = data.location
    cam.hls_url = data.hls_url
    cam.active = data.active
    try:
        cam.rtsp_url = data.rtsp_url
    except Exception:
        pass
    db.add(cam)
    await db.commit()
    return _camera_dict(cam)


@camera_router.delete("/{cam_id}")
async def delete_camera(condo_id: int, cam_id: int, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    cam = await db.get(Camera, cam_id)
    if not cam or cam.condo_id != condo_id:
        raise HTTPException(status_code=404)
    await db.delete(cam)
    await db.commit()
    return {"status": "ok"}


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



amenity_router = APIRouter(prefix="/condos/{condo_id}/amenities")


class AmenityCreate(BaseModel):
    name: str
    type: str = "salao_festas"
    capacity: int = 50
    rules: Optional[str] = None
    available_start: str = "08:00"
    available_end: str = "22:00"
    max_hours: int = 4
    requires_approval: bool = True


@amenity_router.get("")
async def list_amenities(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Amenity).where(Amenity.condo_id == condo_id))
    return [{"id": a.id, "name": a.name, "type": a.type, "capacity": a.capacity,
             "rules": a.rules, "available_start": a.available_start, "available_end": a.available_end,
             "max_hours": a.max_hours, "requires_approval": a.requires_approval} for a in result.all()]


@amenity_router.post("", status_code=201)
async def create_amenity(condo_id: int, data: AmenityCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    amenity = Amenity(name=data.name, type=data.type, capacity=data.capacity,
                      rules=data.rules, available_start=data.available_start,
                      available_end=data.available_end, max_hours=data.max_hours,
                      requires_approval=data.requires_approval, condo_id=condo_id)
    db.add(amenity)
    await db.commit()
    await db.refresh(amenity)
    return {"id": amenity.id, "name": amenity.name, "type": amenity.type,
            "capacity": amenity.capacity, "requires_approval": amenity.requires_approval}


@amenity_router.put("/{amenity_id}")
async def update_amenity(condo_id: int, amenity_id: int, data: AmenityCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    amenity = await db.get(Amenity, amenity_id)
    if not amenity or amenity.condo_id != condo_id:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump().items():
        setattr(amenity, k, v)
    db.add(amenity)
    await db.commit()
    return {"id": amenity.id, "name": amenity.name}


@amenity_router.delete("/{amenity_id}", status_code=204)
async def delete_amenity(condo_id: int, amenity_id: int, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    amenity = await db.get(Amenity, amenity_id)
    if not amenity or amenity.condo_id != condo_id:
        raise HTTPException(status_code=404)
    await db.delete(amenity)
    await db.commit()

router.include_router(apt_router)
router.include_router(parking_router)
router.include_router(camera_router)
router.include_router(resident_router)
router.include_router(amenity_router)
