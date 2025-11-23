# app/services/monitor_service.py
import asyncio
from datetime import datetime
from typing import Tuple, List, Dict, Any

from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd,
)

from app.config import settings

# Memoria para último OK por router (para /estado)
LAST_OK: Dict[str, datetime] = {}


# ---------- Helpers SNMP genéricos ----------

async def snmp_get(host: str, oid: str, community: str | None = None) -> int:
    """
    Hace un SNMP GET y regresa el valor como int.
    Lanza Exception si hay error.
    """
    if community is None:
        community = settings.SNMP_COMMUNITY

    engine = SnmpEngine()
    error_indication, error_status, error_index, var_binds = await getCmd(
        engine,
        CommunityData(community, mpModel=1),            # v2c
        UdpTransportTarget((host, 161), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )

    if error_indication:
        raise RuntimeError(f"SNMP error: {error_indication}")
    if error_status:
        raise RuntimeError(
            f"{error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}"
        )

    for oid, val in var_binds:
        return int(val)

    raise RuntimeError("SNMP: no varBinds")


async def snmp_get_if_octets(
    host: str,
    if_index: int,
    community: str | None = None,
) -> Tuple[int, int]:
    """
    Regresa (ifInOctets, ifOutOctets) de una interfaz.
    OIDs IF-MIB:
      ifInOctets  = 1.3.6.1.2.1.2.2.1.10.X
      ifOutOctets = 1.3.6.1.2.1.2.2.1.16.X
    """
    in_oid = f"1.3.6.1.2.1.2.2.1.10.{if_index}"
    out_oid = f"1.3.6.1.2.1.2.2.1.16.{if_index}"

    in_octets = await snmp_get(host, in_oid, community)
    out_octets = await snmp_get(host, out_oid, community)
    return in_octets, out_octets


async def snmp_get_sysuptime(
    host: str,
    community: str | None = None,
) -> int:
    """
    Regresa sysUpTime en ticks (1/100 segundos).
    OID: 1.3.6.1.2.1.1.3.0
    """
    oid = "1.3.6.1.2.1.1.3.0"
    return await snmp_get(host, oid, community)


# ---------- Lógica de monitoreo de octetos ----------

async def monitor_interface_octets(
    host: str,
    if_index: int,
    seconds: int,
    community: str | None = None,
) -> Dict[str, Any]:
    """
    Durante 'seconds' segundos consulta los octetos y calcula
    el tráfico promedio in/out (bps) por intervalos de 1 segundo.

    Regresa:
      {
        "samples": [
          {"t": 1, "in_bps": ..., "out_bps": ...},
          ...
        ],
        "avg_in_bps": ...,
        "avg_out_bps": ...,
        "last_in_octets": ...,
        "last_out_octets": ...
      }
    """
    if seconds < 1:
        seconds = 1

    # Primer muestreo
    prev_in, prev_out = await snmp_get_if_octets(host, if_index, community)
    samples: List[Dict[str, float]] = []

    for t in range(1, seconds + 1):
        await asyncio.sleep(1)
        cur_in, cur_out = await snmp_get_if_octets(host, if_index, community)

        # manejar posible wrap de contador (32 bits)
        delta_in = cur_in - prev_in
        delta_out = cur_out - prev_out
        if delta_in < 0:
            delta_in += 2**32
        if delta_out < 0:
            delta_out += 2**32

        in_bps = (delta_in * 8) / 1.0
        out_bps = (delta_out * 8) / 1.0

        samples.append({"t": t, "in_bps": in_bps, "out_bps": out_bps})

        prev_in, prev_out = cur_in, cur_out

    if samples:
        avg_in = sum(s["in_bps"] for s in samples) / len(samples)
        avg_out = sum(s["out_bps"] for s in samples) / len(samples)
    else:
        avg_in = avg_out = 0.0

    return {
        "samples": samples,
        "avg_in_bps": avg_in,
        "avg_out_bps": avg_out,
        "last_in_octets": prev_in,
        "last_out_octets": prev_out,
    }


# ---------- Lógica de estado del router ----------

async def get_router_state(host: str, community: str | None = None) -> Dict[str, Any]:
    """
    Intenta hacer SNMP GET a sysUpTime.
    Si responde: estado = UP, guarda timestamp de último OK.
    Si falla: estado = DOWN, calcula tiempo sin respuesta si se conoce.
    """
    global LAST_OK
    now = datetime.utcnow()

    try:
        uptime_ticks = await snmp_get_sysuptime(host, community)
        LAST_OK[host] = now
        uptime_seconds = uptime_ticks / 100.0

        return {
            "estado": "UP",
            "uptime_seconds": uptime_seconds,
            "tiempo_sin_respuesta": 0.0,
            "ultima_respuesta": now.isoformat() + "Z",
        }
    except Exception as e:
        last_ok = LAST_OK.get(host)
        if last_ok:
            sin_resp = (now - last_ok).total_seconds()
            last_ok_str = last_ok.isoformat() + "Z"
        else:
            sin_resp = None
            last_ok_str = None

        return {
            "estado": "DOWN",
            "uptime_seconds": None,
            "tiempo_sin_respuesta": sin_resp,
            "ultima_respuesta": last_ok_str,
            "error": str(e),
        }
