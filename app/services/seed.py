"""
Script de seed inicial: cria o superadmin e um condomínio de demonstração.
Executar: python3 -m app.services.seed
"""
import asyncio
import os
import sys
import bcrypt
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import engine, create_tables
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from models import User, Condo, UserRole, Amenity, AmenityType, Camera

SUPERADMIN_EMAIL = "admin@kas.app"
SUPERADMIN_PASSWORD = "Kas@2026!admin"


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def seed():
    await create_tables()
    async with AsyncSession(engine) as db:
        # Superadmin
        existing = await db.exec(select(User).where(User.email == SUPERADMIN_EMAIL))
        if not existing.first():
            admin = User(
                name="Super Admin KAS",
                email=SUPERADMIN_EMAIL,
                hashed_password=_hash(SUPERADMIN_PASSWORD),
                role=UserRole.superadmin,
            )
            db.add(admin)
            print(f"Superadmin criado: {SUPERADMIN_EMAIL} / {SUPERADMIN_PASSWORD}")
        else:
            print("Superadmin ja existe")

        # Condomínio demo
        existing_condo = await db.exec(select(Condo).where(Condo.slug == "demo"))
        if not existing_condo.first():
            condo = Condo(
                name="Residencial Demo",
                slug="demo",
                address="Rua das Flores, 100",
                city="Sao Paulo",
                state="SP",
                plan="pro",
            )
            db.add(condo)
            await db.commit()
            await db.refresh(condo)

            db.add(Amenity(name="Salao de Festas", type=AmenityType.salao_festas, capacity=80, condo_id=condo.id, requires_approval=True))
            db.add(Amenity(name="Piscina", type=AmenityType.piscina, capacity=30, condo_id=condo.id, requires_approval=False))
            db.add(Amenity(name="Churrasqueira", type=AmenityType.churrasqueira, capacity=20, condo_id=condo.id))

            db.add(Camera(name="Entrada Principal", location="Portao principal", hls_url="http://demo.stream/cam1.m3u8", condo_id=condo.id))
            db.add(Camera(name="Estacionamento", location="Area de vagas", hls_url="http://demo.stream/cam2.m3u8", condo_id=condo.id))

            sindico = User(
                name="Joao Sindico",
                email="sindico@demo.app",
                hashed_password=_hash("Demo@123"),
                role=UserRole.sindico,
                condo_id=condo.id,
            )
            db.add(sindico)

            morador = User(
                name="Maria Moradora",
                email="morador@demo.app",
                hashed_password=_hash("Demo@123"),
                role=UserRole.morador,
                condo_id=condo.id,
                apt_number="101",
                sip_user="8101",
                sip_password="morador123",
            )
            db.add(morador)

            await db.commit()
            print(f"Condominio demo criado (id={condo.id})")
            print("Sindico: sindico@demo.app / Demo@123")
            print("Morador: morador@demo.app / Demo@123 (Apt 101)")
        else:
            print("Condominio demo ja existe")


if __name__ == "__main__":
    asyncio.run(seed())
