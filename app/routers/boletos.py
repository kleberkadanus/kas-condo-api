import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import Optional, List
from database import get_session
from models import Boleto, Apartment, User
from auth_utils import get_current_user, require_sindico
from datetime import datetime, date

router = APIRouter(prefix="/condos/{condo_id}/boletos")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads/boletos")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/mine", response_model=List[dict])
async def my_boletos(condo_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if not user.apt_number:
        return []
    apt = await db.exec(
        select(Apartment).where(Apartment.condo_id == condo_id, Apartment.number == user.apt_number)
    )
    apt = apt.first()
    if not apt:
        return []
    result = await db.exec(
        select(Boleto).where(Boleto.apt_id == apt.id).order_by(Boleto.year.desc(), Boleto.month.desc())
    )
    return [_boleto_dict(b) for b in result.all()]


@router.get("", response_model=List[dict])
async def all_boletos(
    condo_id: int, month: Optional[int] = None, year: Optional[int] = None,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    q = select(Boleto).where(Boleto.condo_id == condo_id)
    if month:
        q = q.where(Boleto.month == month)
    if year:
        q = q.where(Boleto.year == year)
    result = await db.exec(q.order_by(Boleto.apt_number))
    return [_boleto_dict(b) for b in result.all()]


@router.post("/upload")
async def upload_boleto(
    condo_id: int,
    apt_number: str = Form(...),
    month: int = Form(...),
    year: int = Form(...),
    amount: float = Form(...),
    due_date: str = Form(...),
    description: Optional[str] = Form(None),
    pdf: UploadFile = File(...),
    user: User = Depends(require_sindico),
    db: AsyncSession = Depends(get_session),
):
    # Busca ou cria o apartamento
    apt = await db.exec(
        select(Apartment).where(Apartment.condo_id == condo_id, Apartment.number == apt_number)
    )
    apt = apt.first()
    if not apt:
        apt = Apartment(number=apt_number, condo_id=condo_id)
        db.add(apt)
        await db.commit()
        await db.refresh(apt)

    # Salva PDF
    filename = f"{condo_id}_{apt_number}_{year}_{month:02d}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
    content = await pdf.read()
    with open(filepath, "wb") as f:
        f.write(content)

    vps_host = os.getenv("VPS_HOST", "localhost")
    pdf_url = f"http://{vps_host}:8090/uploads/boletos/{filename}"

    boleto = Boleto(
        apt_id=apt.id,
        apt_number=apt_number,
        condo_id=condo_id,
        month=month,
        year=year,
        amount=amount,
        due_date=date.fromisoformat(due_date),
        pdf_url=pdf_url,
        description=description,
    )
    db.add(boleto)
    await db.commit()
    await db.refresh(boleto)
    return _boleto_dict(boleto)


@router.post("/{boleto_id}/paid")
async def mark_paid(
    condo_id: int, boleto_id: int,
    user: User = Depends(require_sindico), db: AsyncSession = Depends(get_session),
):
    boleto = await db.get(Boleto, boleto_id)
    if not boleto or boleto.condo_id != condo_id:
        raise HTTPException(status_code=404)
    boleto.paid = True
    boleto.paid_at = datetime.utcnow()
    db.add(boleto)
    await db.commit()
    return _boleto_dict(boleto)


def _boleto_dict(b: Boleto) -> dict:
    return {
        "id": b.id, "apt_id": b.apt_id, "apt_number": b.apt_number,
        "condo_id": b.condo_id, "month": b.month, "year": b.year,
        "amount": b.amount, "due_date": b.due_date.isoformat(),
        "paid": b.paid, "paid_at": b.paid_at.isoformat() if b.paid_at else None,
        "pdf_url": b.pdf_url, "description": b.description,
    }
