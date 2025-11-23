# app/main.py
from fastapi import FastAPI
from .config import settings
from .db import engine, Base
from .routers import ping, usuarios, routers as routers_api, ssh_test,snmp_test, topologia
from .routers import monitor


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

# Incluir routers
app.include_router(ping.router)
app.include_router(usuarios.router)
app.include_router(routers_api.router)
app.include_router(ssh_test.router)
app.include_router(snmp_test.router)
app.include_router(topologia.router)
app.include_router(monitor.router)



@app.on_event("startup")
async def startup_event():
    # Crear tablas de la BD si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {
        "message": "API de redes funcionando",
        "version": settings.APP_VERSION,
    }
