from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import logging

from database import create_tables
from routers import auth, condos, announcements, bookings, boletos, notifications, admin

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="KAS Condo API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, tags=["auth"])
app.include_router(condos.router, tags=["condos"])
app.include_router(announcements.router, tags=["announcements"])
app.include_router(bookings.router, tags=["bookings"])
app.include_router(boletos.router, tags=["boletos"])
app.include_router(notifications.router, tags=["notifications"])
app.include_router(admin.router, tags=["admin"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kas-condo-api", "version": "1.0.0"}
