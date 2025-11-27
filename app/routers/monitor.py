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
    get_interface_state, 
    start_trap_capture,  
    stop_trap_capture,   
)

import io
import matplotlib.pyplot as plt
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/routers", tags=["Monitoreo"])

# ----------------- MEMORIA DE MONITOREO -----------------
# key = "<hostname>:<if_index>"
# value = {
#   "seconds": int,
#   "data": {
#       "samples": [...],
#       "avg_in_bps": ...,
#       "avg_out_bps": ...,
#       "last_in_octets": ...,
#       "last_out_octets": ...
#   }
# }
MONITOREOS_OCTETOS: Dict[str, Dict[str, Any]] = {}


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
    
class TrapEvent(BaseModel):
    timestamp: str
    event: str
    old_status: int | None = None
    new_status: int | None = None


class EstadoInterfazResponse(BaseModel):
    host: str
    if_index: int
    admin_status: int
    oper_status: int
    admin_status_text: str
    oper_status_text: str
    trap_capture_active: bool
    last_change: str | None = None
    events: List[TrapEvent] = []


class MonitorState(BaseModel):
    """
    Estado lógico del monitoreo de octetos en una interfaz.
    Se usa como respuesta para POST y DELETE.
    """
    hostname: str
    if_index: int
    tiempo: int
    running: bool
    samples_count: int
    avg_in_bps: float | None = None
    avg_out_bps: float | None = None


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


def _build_monitor_key(hostname: str, if_index: int) -> str:
    return f"{hostname}:{if_index}"


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
    Regresa los datos de monitoreo de octetos de la interfaz.

    Comportamiento:
      1) Si existe un monitoreo guardado para (hostname, if_index),
         regresa esas muestras (todas las que se tengan hasta el momento).
      2) Si NO existe, hace un muestreo “en vivo” durante `tiempo` segundos
         y regresa el resultado (sin guardarlo).
    """
    router = await get_router_by_hostname(hostname, db)
    key = _build_monitor_key(router.hostname, if_index)

    entry = MONITOREOS_OCTETOS.get(key)

    if entry is not None:
        # Usar los datos ya muestreados y almacenados
        data = entry["data"]
    else:
        # Muestreo en vivo de respaldo (como tenías originalmente)
        data = await monitor_interface_octets(
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


# --------- POST /routers/{hostname}/interfaces/{if_index}/octetos/{tiempo} ---------


@router.post(
    "/{hostname}/interfaces/{if_index}/octetos/{tiempo}",
    response_model=MonitorState,
)
async def iniciar_monitoreo_octetos(
    hostname: str,
    if_index: int,
    tiempo: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Activa el monitoreo de octetos de entrada/salida en la interfaz
    correspondiente durante `tiempo` segundos.

    Hace el muestreo (SNMP) en este momento, guarda el resultado en memoria
    y regresa el estado lógico del monitoreo.
    """
    if tiempo < 1:
        raise HTTPException(status_code=400, detail="El tiempo debe ser >= 1 segundo")

    router = await get_router_by_hostname(hostname, db)
    key = _build_monitor_key(router.hostname, if_index)

    # Ejecuta el muestreo real vía SNMP
    data = await monitor_interface_octets(
        host=router.ip_admin,
        if_index=if_index,
        seconds=tiempo,
    )

    # Guarda en memoria para futuros GET
    MONITOREOS_OCTETOS[key] = {
        "seconds": tiempo,
        "data": data,
    }

    return MonitorState(
        hostname=router.hostname,
        if_index=if_index,
        tiempo=tiempo,
        running=False,  # ya terminó el muestreo (fue síncrono)
        samples_count=len(data["samples"]),
        avg_in_bps=data["avg_in_bps"],
        avg_out_bps=data["avg_out_bps"],
    )


# --------- DELETE /routers/{hostname}/interfaces/{if_index}/octetos/{tiempo} ---------


@router.delete(
    "/{hostname}/interfaces/{if_index}/octetos/{tiempo}",
    response_model=MonitorState,
)
async def detener_monitoreo_octetos(
    hostname: str,
    if_index: int,
    tiempo: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Para (lógicamente) el proceso de monitoreo de octetos de la interfaz,
    borrando los datos almacenados en memoria para esa interfaz.

    Regresa el último estado que se tenía antes de eliminarlo.
    """
    router = await get_router_by_hostname(hostname, db)
    key = _build_monitor_key(router.hostname, if_index)

    entry = MONITOREOS_OCTETOS.pop(key, None)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="No hay monitoreo activo (o datos almacenados) para esa interfaz",
        )

    data = entry["data"]
    segundos = entry.get("seconds", tiempo)

    return MonitorState(
        hostname=router.hostname,
        if_index=if_index,
        tiempo=segundos,
        running=False,
        samples_count=len(data["samples"]),
        avg_in_bps=data["avg_in_bps"],
        avg_out_bps=data["avg_out_bps"],
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




@router.get("/{hostname}/interfaces/{if_index}/grafica")
async def grafica_monitoreo_interfaz(
    hostname: str,
    if_index: int,
    segundos: int = 10,   # puedes cambiar el default si quieres
    db: AsyncSession = Depends(get_db),
):
    """
    GET /routers/{hostname}/interfaces/{if_index}/grafica

    Genera una imagen PNG con la gráfica del monitoreo de octetos
    de la interfaz indicada (ifIndex SNMP).

    Usa internamente monitor_interface_octets para tomar muestras
    durante 'segundos' segundos.
    """
    # 1) Verificar que el router exista en la BD
    router = await get_router_by_hostname(hostname, db)

    # 2) Obtener muestras de tráfico con la misma función que /octetos/{tiempo}
    data: Dict[str, Any] = await monitor_interface_octets(
        host=router.ip_admin,
        if_index=if_index,
        seconds=segundos,
    )

    samples = data.get("samples", [])

    # 3) Construir la gráfica con matplotlib
    fig = plt.figure(figsize=(6, 4))

    if samples:
        t = [s["t"] for s in samples]
        in_bps = [s["in_bps"] for s in samples]
        out_bps = [s["out_bps"] for s in samples]

        plt.plot(t, in_bps, label="In bps")
        plt.plot(t, out_bps, label="Out bps")

        plt.xlabel("Tiempo (s)")
        plt.ylabel("Tráfico (bps)")
        plt.title(f"{hostname} - ifIndex {if_index}")
        plt.legend()
        plt.grid(True)
    else:
        # Si por alguna razón no hay samples, mostramos un mensaje
        plt.text(
            0.5,
            0.5,
            "Sin datos de monitoreo",
            ha="center",
            va="center",
            fontsize=12,
        )
        plt.axis("off")

    # 4) Enviar la imagen como respuesta HTTP
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")


@router.get(
    "/{hostname}/interfaces/{if_index}/estado",
    response_model=EstadoInterfazResponse,
)
async def obtener_estado_interfaz(
    hostname: str,
    if_index: int,
    db: AsyncSession = Depends(get_db),
):
    """
    GET /routers/{hostname}/interfaces/{if_index}/estado
    Regresa un json con el estado de la interfaz.
    """
    router = await get_router_by_hostname(hostname, db)

    data = await get_interface_state(router.ip_admin, if_index)
    events = [TrapEvent(**e) for e in data.get("events", [])]

    return EstadoInterfazResponse(
        host=data["host"],
        if_index=data["if_index"],
        admin_status=data["admin_status"],
        oper_status=data["oper_status"],
        admin_status_text=data["admin_status_text"],
        oper_status_text=data["oper_status_text"],
        trap_capture_active=data["trap_capture_active"],
        last_change=data["last_change"],
        events=events,
    )


@router.post(
    "/{hostname}/interfaces/{if_index}/estado",
    response_model=EstadoInterfazResponse,
)
async def activar_trampas_link(
    hostname: str,
    if_index: int,
    db: AsyncSession = Depends(get_db),
):
    """
    POST /routers/{hostname}/interfaces/{if_index}/estado
    Activa la captura de trampas linkup/linkdown en esa interfaz.
    """
    router = await get_router_by_hostname(hostname, db)

    data = await start_trap_capture(router.ip_admin, if_index)
    events = [TrapEvent(**e) for e in data.get("events", [])]

    return EstadoInterfazResponse(
        host=data["host"],
        if_index=data["if_index"],
        admin_status=data["admin_status"],
        oper_status=data["oper_status"],
        admin_status_text=data["admin_status_text"],
        oper_status_text=data["oper_status_text"],
        trap_capture_active=data["trap_capture_active"],
        last_change=data["last_change"],
        events=events,
    )


@router.delete(
    "/{hostname}/interfaces/{if_index}/estado",
    response_model=EstadoInterfazResponse,
)
async def detener_trampas_link(
    hostname: str,
    if_index: int,
    db: AsyncSession = Depends(get_db),
):
    """
    DELETE /routers/{hostname}/interfaces/{if_index}/estado
    Detiene la captura de trampas linkup/linkdown en esa interfaz.
    """
    router = await get_router_by_hostname(hostname, db)

    data = await stop_trap_capture(router.ip_admin, if_index)
    events = [TrapEvent(**e) for e in data.get("events", [])]

    return EstadoInterfazResponse(
        host=data["host"],
        if_index=data["if_index"],
        admin_status=data["admin_status"],
        oper_status=data["oper_status"],
        admin_status_text=data["admin_status_text"],
        oper_status_text=data["oper_status_text"],
        trap_capture_active=data["trap_capture_active"],
        last_change=data["last_change"],
        events=events,
    )