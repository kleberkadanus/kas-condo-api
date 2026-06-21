from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
import uuid


class UserRole(str, Enum):
    superadmin = "superadmin"
    sindico = "sindico"
    zelador = "zelador"
    morador = "morador"
    portaria = "portaria"


class PlanType(str, Enum):
    basic = "basic"
    pro = "pro"
    enterprise = "enterprise"


class BookingStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class AnnouncementCategory(str, Enum):
    aviso = "aviso"
    manutencao = "manutencao"
    evento = "evento"
    financeiro = "financeiro"


class AmenityType(str, Enum):
    salao_festas = "salao_festas"
    piscina = "piscina"
    churrasqueira = "churrasqueira"
    academia = "academia"
    quadra = "quadra"
    outro = "outro"


# ─── CONDOMÍNIO ───────────────────────────────────────────────────

class Condo(SQLModel, table=True):
    __tablename__ = "condos"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)
    address: str = ""
    city: str = ""
    state: str = "SP"
    plan: PlanType = PlanType.basic
    active: bool = True
    logo_url: Optional[str] = None
    portaria_extension: str = "9000"
    sip_domain: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    users: List["User"] = Relationship(back_populates="condo")
    apartments: List["Apartment"] = Relationship(back_populates="condo")
    amenities: List["Amenity"] = Relationship(back_populates="condo")
    announcements: List["Announcement"] = Relationship(back_populates="condo")
    cameras: List["Camera"] = Relationship(back_populates="condo")


# ─── USUÁRIO ─────────────────────────────────────────────────────

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole = UserRole.morador
    condo_id: Optional[int] = Field(default=None, foreign_key="condos.id")
    apt_number: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    sip_user: Optional[str] = None
    sip_password: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    condo: Optional[Condo] = Relationship(back_populates="users")
    push_tokens: List["PushToken"] = Relationship(back_populates="user")


# ─── APARTAMENTO ─────────────────────────────────────────────────

class Apartment(SQLModel, table=True):
    __tablename__ = "apartments"
    id: Optional[int] = Field(default=None, primary_key=True)
    number: str
    block: Optional[str] = None
    floor: Optional[int] = None
    condo_id: int = Field(foreign_key="condos.id")
    owner_id: Optional[int] = Field(default=None, foreign_key="users.id")

    condo: Optional[Condo] = Relationship(back_populates="apartments")
    parking_slots: List["ParkingSlot"] = Relationship(back_populates="apartment")
    boletos: List["Boleto"] = Relationship(back_populates="apartment")


# ─── VAGA ────────────────────────────────────────────────────────

class ParkingSlot(SQLModel, table=True):
    __tablename__ = "parking_slots"
    id: Optional[int] = Field(default=None, primary_key=True)
    number: str
    type: str = "covered"  # covered | uncovered
    condo_id: int = Field(foreign_key="condos.id")
    apt_id: Optional[int] = Field(default=None, foreign_key="apartments.id")

    apartment: Optional[Apartment] = Relationship(back_populates="parking_slots")


# ─── AVISO ───────────────────────────────────────────────────────

class Announcement(SQLModel, table=True):
    __tablename__ = "announcements"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    category: AnnouncementCategory = AnnouncementCategory.aviso
    pinned: bool = False
    condo_id: int = Field(foreign_key="condos.id")
    author_id: int = Field(foreign_key="users.id")
    author_name: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    condo: Optional[Condo] = Relationship(back_populates="announcements")


# ─── ESPAÇO / COMODIDADE ─────────────────────────────────────────

class Amenity(SQLModel, table=True):
    __tablename__ = "amenities"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: AmenityType = AmenityType.salao_festas
    capacity: int = 50
    rules: Optional[str] = None
    available_start: str = "08:00"
    available_end: str = "22:00"
    max_hours: int = 4
    requires_approval: bool = True
    condo_id: int = Field(foreign_key="condos.id")

    condo: Optional[Condo] = Relationship(back_populates="amenities")
    bookings: List["Booking"] = Relationship(back_populates="amenity")


# ─── RESERVA ─────────────────────────────────────────────────────

class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    id: Optional[int] = Field(default=None, primary_key=True)
    amenity_id: int = Field(foreign_key="amenities.id")
    user_id: int = Field(foreign_key="users.id")
    user_name: str = ""
    apt_number: str = ""
    date: date
    start_time: str
    end_time: str
    status: BookingStatus = BookingStatus.pending
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    amenity: Optional[Amenity] = Relationship(back_populates="bookings")


# ─── BOLETO ──────────────────────────────────────────────────────

class Boleto(SQLModel, table=True):
    __tablename__ = "boletos"
    id: Optional[int] = Field(default=None, primary_key=True)
    apt_id: int = Field(foreign_key="apartments.id")
    apt_number: str = ""
    condo_id: int = Field(foreign_key="condos.id")
    month: int
    year: int
    amount: float
    due_date: date
    paid: bool = False
    paid_at: Optional[datetime] = None
    pdf_url: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    apartment: Optional[Apartment] = Relationship(back_populates="boletos")


# ─── CÂMERA ──────────────────────────────────────────────────────

class Camera(SQLModel, table=True):
    __tablename__ = "cameras"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    location: str
    hls_url: str
    condo_id: int = Field(foreign_key="condos.id")
    active: bool = True

    condo: Optional[Condo] = Relationship(back_populates="cameras")


# ─── PUSH TOKEN ───────────────────────────────────────────────────

class PushToken(SQLModel, table=True):
    __tablename__ = "push_tokens"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    token: str = Field(index=True)
    platform: str = "android"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="push_tokens")
