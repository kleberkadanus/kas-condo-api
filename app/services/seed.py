"""
Script de seed inicial: cria o superadmin e um condomínio de demonstração.
Executar: python3 -m app.services.seed
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import engine, create_tables
from sqlmodel import Session, SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Condo, UserRole, Amenity, AmenityType, Camera
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SUPERADMIN_EMAIL = "admin@kas.app"
SUPERADMIN_PASSWORD = "Kas@2026!admin"


async def seed():
    await create_tables()
    async with AsyncSession(engine) as db:
        # Superadmin
        existing = await db.exec(select(User).where(User.email == SUPERADMIN_EMAIL))
        if not existing.first():
            admin = User(
                name="Super Admin KAS",
                email=SUPERADMIN_EMAIL,
                hashed_password=pwd_context.hash(SUPERADMIN_PASSWORD),
                role=UserRole.superadmin,
            )
            db.add(admin)
            print(f"✅ Superadmin criado: {SUPERADMIN_EMAIL} / {SUPERADMIN_PASSWORD}")
        else:
            print("ℹ️  Superadmin já existe")

        # Condomínio demo
        existing_condo = await db.exec(select(Condo).where(Condo.slug == "demo"))
        if not existing_condo.first():
            condo = Condo(
                name="Residencial Demo",
                slug="demo",
                address="Rua das Flores, 100",
                city="São Paulo",
                state="SP",
                plan="pro",
            )
            db.add(condo)
            await db.commit()
            await db.refresh(condo)

            # Amenidades demo
            db.add(Amenity(name="Salão de Festas", type=AmenityType.salao_festas, capacity=80, condo_id=condo.id, requires_approval=True))
            db.add(Amenity(name="Piscina", type=AmenityType.piscina, capacity=30, condo_id=condo.id, requires_approval=False))
            db.add(Amenity(name="Churrasqueira", type=AmenityType.churrasqueira, capacity=20, condo_id=condo.id))

            # Câmera demo
            db.add(Camera(name="Entrada Principal", location="Portão principal", hls_url="http://demo.stream/cam1.m3u8", condo_id=condo.id))
            db.add(Camera(name="Estacionamento", location="Área de vagas", hls_url="http://demo.stream/cam2.m3u8", condo_id=condo.id))

            # Síndico demo
            sindico = User(
                name="João Síndico",
                email="sindico@demo.app",
                hashed_password=pwd_context.hash("Demo@123"),
                role=UserRole.sindico,
                condo_id=condo.id,
            )
            db.add(sindico)

            # Morador demo
            morador = User(
                name="Maria Moradora",
                email="morador@demo.app",
                hashed_password=pwd_context.hash("Demo@123"),
                role=UserRole.morador,
                condo_id=condo.id,
                apt_number="101",
                sip_user="8101",
                sip_password="morador123",
            )
            db.add(morador)

            await db.commit()
            print(f"✅ Condomínio demo criado (id={condo.id})")
            print("   Síndico: sindico@demo.app / Demo@123")
            print("   Morador: morador@demo.app / Demo@123 (Apt 101)")
        else:
            print("ℹ️  Condomínio demo já existe")


if __name__ == "__main__":
    asyncio.run(seed())
