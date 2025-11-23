# app/routers/monitor.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.router import Router
from app.services.monitor_service import (
    monitor_interface_octets,
    get_router_state,
)

router = APIRouter(prefix="/routers", tags=["Monitoreo"])


class Sample(BaseModel):
    t: int
    in_bps: float
    out_bps: float


class OctetosResponse(BaseModel):
    samples: List[Sample]
    avg_in_bps: float
    avg_out_bps: float
    last_in_octets: int
    last_out_octets: int


class EstadoRouterResponse(BaseModel):
    estado: str
    uptime_seconds: float | None = None
    tiempo_sin_respuesta: float | None = None
    ultima_respuesta: str | None = None
    error: str | None = None


async def get_router_by_hostname(
    hostname: str, db: AsyncSession
) -> Router:
    result = await db.execute(
        select(Router).where(Router.hostname == hostname)
    )
    router = result.scalar_one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    return router


# --------- GET /routers/{hostname}/interfaces/{if_index}/octetos/{tiempo} ---------


@router.get(
    "/{hostname}/interfaces/{if_index}/octetos/{tiempo}",
    response_model=OctetosResponse,
)
async def obtener_octetos_interfaz(
    hostname: str,
    if_index: int,
    tiempo: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Regresa en formato json:
      - octetos recibidos/transmitidos al final del periodo
      - tráfico promedio in/out en bps
      - muestras por segundo durante 'tiempo' segundos

    Nota: 'if_index' es el ifIndex SNMP de la interfaz.
    """
    router = await get_router_by_hostname(hostname, db)

    data: Dict[str, Any] = await monitor_interface_octets(
        host=router.ip_admin,
        if_index=if_index,
        seconds=tiempo,
    )

    return OctetosResponse(
        samples=[Sample(**s) for s in data["samples"]],
        avg_in_bps=data["avg_in_bps"],
        avg_out_bps=data["avg_out_bps"],
        last_in_octets=data["last_in_octets"],
        last_out_octets=data["last_out_octets"],
    )


# --------- GET /routers/{hostname}/estado ---------


@router.get(
    "/{hostname}/estado",
    response_model=EstadoRouterResponse,
)
async def obtener_estado_router(
    hostname: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Regresa estado general del router usando SNMP:
      - estado: UP/DOWN
      - uptime_seconds
      - tiempo_sin_respuesta
      - ultima_respuesta
    """
    router = await get_router_by_hostname(hostname, db)

    data = await get_router_state(router.ip_admin)

    return EstadoRouterResponse(**data)
