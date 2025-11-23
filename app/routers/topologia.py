# app/routers/topologia.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.router import Router, Interface

import io
import networkx as nx
import matplotlib.pyplot as plt
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/topologia", tags=["Topología"])

# ----------------- ESTADO DEL “DEMONIO” -----------------
DEMON_RUNNING: bool = False
DEMON_INTERVAL: int = 300  # segundos (5 minutos por defecto)


# ----------------- ESQUEMAS Pydantic -----------------

class RouterNode(BaseModel):
    hostname: str
    ip_admin: Optional[str] = None
    loopback: Optional[str] = None
    role: Optional[str] = None
    vendor: Optional[str] = None
    os_version: Optional[str] = None


class Link(BaseModel):
    source: str
    target: str
    interface: Optional[str] = None


class DaemonState(BaseModel):
    running: bool
    interval_seconds: int


class TopologyRead(BaseModel):
    routers: List[RouterNode]
    enlaces: List[Link]
    daemon: DaemonState


class DaemonUpdate(BaseModel):
    interval_seconds: int


# ----------------- FUNCIÓN INTERNA: construir topología -----------------


async def build_topology(db: AsyncSession) -> TopologyRead:
    result = await db.execute(
        select(Router).options(selectinload(Router.interfaces))
    )
    routers = result.scalars().unique().all()

    router_nodes: List[RouterNode] = []
    enlaces: List[Link] = []

    # Diccionario para ver si existe un router con cierto hostname
    known_hostnames = {r.hostname for r in routers}

    for r in routers:
        router_nodes.append(
            RouterNode(
                hostname=r.hostname,
                ip_admin=r.ip_admin,
                loopback=r.loopback,
                role=r.role,
                vendor=r.vendor,
                os_version=r.os_version,
            )
        )

        for iface in r.interfaces:
            if iface.neighbor_hostname:
                enlaces.append(
                    Link(
                        source=r.hostname,
                        target=iface.neighbor_hostname,
                        interface=iface.name,
                    )
                )
                # Si el vecino no está en la tabla de routers, lo añadimos “huérfano”
                if iface.neighbor_hostname not in known_hostnames:
                    router_nodes.append(
                        RouterNode(
                            hostname=iface.neighbor_hostname,
                            ip_admin=None,
                            loopback=None,
                            role=None,
                            vendor=None,
                            os_version=None,
                        )
                    )
                    known_hostnames.add(iface.neighbor_hostname)

    return TopologyRead(
        routers=router_nodes,
        enlaces=enlaces,
        daemon=DaemonState(
            running=DEMON_RUNNING,
            interval_seconds=DEMON_INTERVAL,
        ),
    )


# ----------------- ENDPOINTS /topologia -----------------


@router.get("/", response_model=TopologyRead)
async def obtener_topologia(db: AsyncSession = Depends(get_db)):
    """
    GET /topologia
    Regresa json con los routers existentes en la topología
    y ligas a sus routers vecinos.
    """
    return await build_topology(db)


@router.post("/", response_model=TopologyRead)
async def iniciar_demonio_topologia(db: AsyncSession = Depends(get_db)):
    """
    POST /topologia
    Activa un “demonio” lógico que cada cierto tiempo
    explora la red (aquí solo guardamos el estado).
    """
    global DEMON_RUNNING
    DEMON_RUNNING = True
    # Aquí en un proyecto grande podrías lanzar un thread/Task
    # que use SSH/SNMP para descubrir cambios.
    return await build_topology(db)


@router.put("/", response_model=DaemonState)
async def actualizar_intervalo_demonio(
    cfg: DaemonUpdate,
):
    """
    PUT /topologia
    Permite cambiar el intervalo de tiempo en el que el demonio
    explora la topología.
    """
    global DEMON_INTERVAL
    DEMON_INTERVAL = cfg.interval_seconds
    return DaemonState(running=DEMON_RUNNING, interval_seconds=DEMON_INTERVAL)


@router.delete("/", response_model=DaemonState)
async def detener_demonio_topologia():
    """
    DELETE /topologia
    Detiene el demonio que explora la topología.
    """
    global DEMON_RUNNING
    DEMON_RUNNING = False
    return DaemonState(running=DEMON_RUNNING, interval_seconds=DEMON_INTERVAL)


# ----------------- /topologia/grafica -----------------


@router.get("/grafica")
async def grafica_topologia(db: AsyncSession = Depends(get_db)):
    """
    GET /topologia/grafica
    Regresa una imagen PNG con la topología actual.
    """
    topo = await build_topology(db)

    G = nx.Graph()
    for r in topo.routers:
        G.add_node(r.hostname)
    for e in topo.enlaces:
        G.add_edge(e.source, e.target)

    # Dibujar grafo
    fig = plt.figure(figsize=(6, 4))
    if G.number_of_nodes() > 0:
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")




