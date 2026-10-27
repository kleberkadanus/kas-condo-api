from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import date as DateType
from database import get_session
from models import Booking, BookingStatus, Amenity, AmenityType, User
from auth_utils import get_current_user, require_sindico

router = APIRouter()

amenity_router = APIRouter(prefix="/condos/{condo_id}/amenities")
booking_router = APIRouter(prefix="/condos/{condo_id}/bookings")


# ─── Amenities ───────────────────────────────────────────────────

@amenity_router.get("", response_model=List[dict])
async def list_amenities(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Amenity).where(Amenity.condo_id == condo_id))
    return [
        {
            "id": a.id, "name": a.name, "type": a.type, "capacity": a.capacity,
            "rules": a.rules, "available_start": a.available_start,
            "available_end": a.available_end, "max_hours": a.max_hours,
            "requires_approval": a.requires_approval, "condo_id": a.condo_id,
        }
        for a in result.all()
    ]


class AmenityCreate(BaseModel):
    name: str
    type: AmenityType = AmenityType.salao_festas
    capacity: int = 50
    rules: Optional[str] = None
    available_start: str = "08:00"
    available_end: str = "22:00"
    max_hours: int = 4
    requires_approval: bool = True


@amenity_router.post("")
async def create_amenity(condo_id: int, data: AmenityCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    amenity = Amenity(**data.model_dump(), condo_id=condo_id)
    db.add(amenity)
    await db.commit()
    await db.refresh(amenity)
    return {
        "id": amenity.id, "name": amenity.name, "type": amenity.type,
        "capacity": amenity.capacity, "rules": amenity.rules,
        "available_start": amenity.available_start, "available_end": amenity.available_end,
        "max_hours": amenity.max_hours, "requires_approval": amenity.requires_approval,
        "condo_id": amenity.condo_id,
    }


@amenity_router.put("/{amenity_id}")
async def update_amenity(condo_id: int, amenity_id: int, data: AmenityCreate, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    amenity = await db.get(Amenity, amenity_id)
    if not amenity or amenity.condo_id != condo_id:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump().items():
        setattr(amenity, k, v)
    db.add(amenity)
    await db.commit()
    return {
        "id": amenity.id, "name": amenity.name, "type": amenity.type,
        "capacity": amenity.capacity, "rules": amenity.rules,
        "available_start": amenity.available_start, "available_end": amenity.available_end,
        "max_hours": amenity.max_hours, "requires_approval": amenity.requires_approval,
    }


@amenity_router.delete("/{amenity_id}")
async def delete_amenity(condo_id: int, amenity_id: int, user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session)):
    amenity = await db.get(Amenity, amenity_id)
    if not amenity or amenity.condo_id != condo_id:
        raise HTTPException(status_code=404)
    await db.delete(amenity)
    await db.commit()
    return {"status": "ok"}


# ─── Bookings ────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    amenity_id: int
    date: DateType
    start_time: str
    end_time: str
    notes: Optional[str] = None


@booking_router.get("", response_model=List[dict])
async def list_bookings(
    condo_id: int, date: Optional[str] = None, amenity_id: Optional[int] = None,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    q = select(Booking).join(Amenity).where(Amenity.condo_id == condo_id)
    if amenity_id:
        q = q.where(Booking.amenity_id == amenity_id)
    result = await db.exec(q.order_by(Booking.date.desc()))
    return [_booking_dict(b) for b in result.all()]


@booking_router.get("/mine", response_model=List[dict])
async def my_bookings(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    result = await db.exec(select(Booking).where(Booking.user_id == user.id).order_by(Booking.date.desc()))
    return [_booking_dict(b) for b in result.all()]


@booking_router.post("")
async def create_booking(
    condo_id: int, data: BookingCreate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    amenity = await db.get(Amenity, data.amenity_id)
    if not amenity or amenity.condo_id != condo_id:
        raise HTTPException(status_code=404, detail="Espaço não encontrado")

    conflict = await db.exec(
        select(Booking).where(
            Booking.amenity_id == data.amenity_id,
            Booking.date == data.date,
            Booking.status.in_([BookingStatus.pending, BookingStatus.approved]),
        )
    )
    existing = conflict.all()
    for e in existing:
        if not (data.end_time <= e.start_time or data.start_time >= e.end_time):
            raise HTTPException(status_code=409, detail="Horário já reservado. Escolha outro horário.")

    status = BookingStatus.pending if amenity.requires_approval else BookingStatus.approved
    booking = Booking(
        amenity_id=data.amenity_id,
        user_id=user.id,
        user_name=user.name,
        apt_number=user.apt_number or "",
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        notes=data.notes,
        status=status,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    result = {**_booking_dict(booking), "amenity_name": amenity.name}
    return result


@booking_router.delete("/{booking_id}")
async def cancel_booking(
    condo_id: int, booking_id: int,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404)
    if booking.user_id != user.id and user.role not in ["sindico", "superadmin"]:
        raise HTTPException(status_code=403)
    booking.status = BookingStatus.cancelled
    db.add(booking)
    await db.commit()
    return {"status": "ok"}


@booking_router.post("/{booking_id}/approve")
async def approve_booking(
    condo_id: int, booking_id: int,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404)
    booking.status = BookingStatus.approved
    db.add(booking)
    await db.commit()
    return _booking_dict(booking)


@booking_router.post("/{booking_id}/reject")
async def reject_booking(
    condo_id: int, booking_id: int,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404)
    booking.status = BookingStatus.rejected
    db.add(booking)
    await db.commit()
    return _booking_dict(booking)


def _booking_dict(b: Booking) -> dict:
    return {
        "id": b.id, "amenity_id": b.amenity_id, "amenity_name": "",
        "user_id": b.user_id, "user_name": b.user_name,
        "apt_number": b.apt_number, "date": b.date.isoformat(),
        "start_time": b.start_time, "end_time": b.end_time,
        "status": b.status, "notes": b.notes,
        "created_at": b.created_at.isoformat(),
    }


router.include_router(amenity_router)
router.include_router(booking_router)
