# app/services/monitor_service.py
import asyncio
import subprocess
from datetime import datetime
from typing import Tuple, List, Dict, Any

from app.config import settings

# Memoria para último OK por router (para /estado)
LAST_OK: Dict[str, datetime] = {}

TRAP_STATE: Dict[tuple[str, int], Dict[str, Any]] = {}

def snmp_get_raw(host: str, oid: str, community: str | None = None) -> int:
    """
    Ejecuta snmpget del sistema y regresa el valor como int.
    Lanza Exception si hay error.
    """
    if community is None:
        community = settings.SNMP_COMMUNITY

    cmd = [
        "snmpget",
        "-v2c",
        "-c",
        community,
        host,
        oid,
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3,
    )

    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"snmpget error: {msg}")

    # Ejemplo de salida:
    # SNMPv2-MIB::sysUpTime.0 = Timeticks: (1234567) 2 days, 3:12:34.00
    # IF-MIB::ifInOctets.1 = Counter32: 123456
    line = proc.stdout.strip()
    # Nos quedamos con la parte después de ":" y convertimos a int si podemos
    try:
        after_equals = line.split("=", 1)[1].strip()
        # after_equals ~ "Counter32: 123456" o "Timeticks: (12345) ..."
        if ":" in after_equals:
            _, val_part = after_equals.split(":", 1)
            val_part = val_part.strip()
        else:
            val_part = after_equals

        # Para Timeticks: (123456) ...
        if val_part.startswith("("):
            num_str = val_part.split(")", 1)[0].strip("() ")
        else:
            # Counter32: 123456
            num_str = val_part.split(" ", 1)[0]

        return int(num_str)
    except Exception as e:
        raise RuntimeError(f"No se pudo parsear la salida SNMP: {line} ({e})")


def snmp_get_if_octets_sync(
    host: str,
    if_index: int,
    community: str | None = None,
) -> Tuple[int, int]:
    """
    Regresa (ifInOctets, ifOutOctets) de una interfaz usando snmpget.
    OIDs IF-MIB:
      ifInOctets  = 1.3.6.1.2.1.2.2.1.10.X
      ifOutOctets = 1.3.6.1.2.1.2.2.1.16.X
    """
    in_oid = f"1.3.6.1.2.1.2.2.1.10.{if_index}"
    out_oid = f"1.3.6.1.2.1.2.2.1.16.{if_index}"

    in_octets = snmp_get_raw(host, in_oid, community)
    out_octets = snmp_get_raw(host, out_oid, community)
    return in_octets, out_octets


def snmp_get_if_status_sync(
    host: str,
    if_index: int,
    community: str | None = None,
) -> Dict[str, Any]:
    """
    Regresa adminStatus y operStatus de una interfaz:
      ifAdminStatus: 1.3.6.1.2.1.2.2.1.7.X
      ifOperStatus : 1.3.6.1.2.1.2.2.1.8.X
    """
    if community is None:
        community = settings.SNMP_COMMUNITY

    admin_oid = f"1.3.6.1.2.1.2.2.1.7.{if_index}"
    oper_oid = f"1.3.6.1.2.1.2.2.1.8.{if_index}"

    admin = snmp_get_raw(host, admin_oid, community)
    oper = snmp_get_raw(host, oper_oid, community)

    admin_map = {
        1: "up",
        2: "down",
        3: "testing",
    }
    oper_map = {
        1: "up",
        2: "down",
        3: "testing",
        4: "unknown",
        5: "dormant",
        6: "notPresent",
        7: "lowerLayerDown",
    }

    return {
        "admin_status": admin,
        "oper_status": oper,
        "admin_status_text": admin_map.get(admin, f"unknown({admin})"),
        "oper_status_text": oper_map.get(oper, f"unknown({oper})"),
    }


async def get_interface_state(
    host: str,
    if_index: int,
    community: str | None = None,
) -> Dict[str, Any]:
    """
    Regresa el estado actual de la interfaz y, si la captura de trampas
    está activa, registra eventos linkUp/linkDown cuando cambia operStatus.
    """
    global TRAP_STATE
    loop = asyncio.get_event_loop()

    status = await loop.run_in_executor(
        None, snmp_get_if_status_sync, host, if_index, community
    )

    key = (host, if_index)
    now = datetime.utcnow()

    info = TRAP_STATE.get(key)
    if info is None:
        info = {
            "active": False,
            "last_oper_status": status["oper_status"],
            "last_change": None,
            "events": [],
        }
        TRAP_STATE[key] = info
    else:
        if info["active"]:
            prev = info.get("last_oper_status")
            cur = status["oper_status"]

            if prev is not None and cur != prev:
                event_name = None
                # Interpretamos cambio como trap lógico
                if prev != 1 and cur == 1:
                    event_name = "linkUp"
                elif prev == 1 and cur != 1:
                    event_name = "linkDown"

                if event_name:
                    ev = {
                        "timestamp": now.isoformat() + "Z",
                        "event": event_name,
                        "old_status": prev,
                        "new_status": cur,
                    }
                    info["events"].append(ev)
                    # Opcional: limitar historial
                    if len(info["events"]) > 100:
                        info["events"] = info["events"][-100:]

                info["last_change"] = now

            info["last_oper_status"] = cur
        else:
            # Si no está activa la captura, solo actualizamos último estado
            info["last_oper_status"] = status["oper_status"]

    return {
        "host": host,
        "if_index": if_index,
        "admin_status": status["admin_status"],
        "oper_status": status["oper_status"],
        "admin_status_text": status["admin_status_text"],
        "oper_status_text": status["oper_status_text"],
        "trap_capture_active": info["active"],
        "last_change": info["last_change"].isoformat() + "Z"
        if info["last_change"]
        else None,
        "events": info["events"],
    }


async def start_trap_capture(
    host: str,
    if_index: int,
    community: str | None = None,
) -> Dict[str, Any]:
    """
    Activa la captura lógica de trampas linkUp/linkDown en una interfaz.
    """
    global TRAP_STATE
    key = (host, if_index)

    loop = asyncio.get_event_loop()
    status = await loop.run_in_executor(
        None, snmp_get_if_status_sync, host, if_index, community
    )

    info = TRAP_STATE.get(key)
    if info is None:
        info = {
            "active": True,
            "last_oper_status": status["oper_status"],
            "last_change": None,
            "events": [],
        }
        TRAP_STATE[key] = info
    else:
        info["active"] = True
        info["last_oper_status"] = status["oper_status"]

    # Regresamos el estado actual (ya con active=True)
    return await get_interface_state(host, if_index, community)


async def stop_trap_capture(
    host: str,
    if_index: int,
    community: str | None = None,
) -> Dict[str, Any]:
    """
    Detiene la captura lógica de trampas linkUp/linkDown en una interfaz.
    """
    global TRAP_STATE
    key = (host, if_index)

    info = TRAP_STATE.get(key)
    if info is None:
        info = {
            "active": False,
            "last_oper_status": None,
            "last_change": None,
            "events": [],
        }
        TRAP_STATE[key] = info
    else:
        info["active"] = False

    return await get_interface_state(host, if_index, community)


def snmp_get_sysuptime_sync(
    host: str,
    community: str | None = None,
) -> int:
    """
    Regresa sysUpTime en ticks (1/100 segundos) con snmpget.
    OID: 1.3.6.1.2.1.1.3.0
    """
    oid = "1.3.6.1.2.1.1.3.0"
    return snmp_get_raw(host, oid, community)


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

    loop = asyncio.get_event_loop()

    # Primer muestreo (en thread, porque subprocess es bloqueante)
    prev_in, prev_out = await loop.run_in_executor(
        None, snmp_get_if_octets_sync, host, if_index, community
    )

    samples: List[Dict[str, float]] = []

    for t in range(1, seconds + 1):
        await asyncio.sleep(1)

        cur_in, cur_out = await loop.run_in_executor(
            None, snmp_get_if_octets_sync, host, if_index, community
        )

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


async def get_router_state(host: str, community: str | None = None) -> Dict[str, Any]:
    """
    Intenta hacer SNMP GET a sysUpTime con snmpget.
    Si responde: estado = UP, guarda timestamp de último OK.
    Si falla: estado = DOWN, calcula tiempo sin respuesta si se conoce.
    """
    global LAST_OK
    now = datetime.utcnow()

    loop = asyncio.get_event_loop()

    try:
        uptime_ticks = await loop.run_in_executor(
            None, snmp_get_sysuptime_sync, host, community
        )
        LAST_OK[host] = now
        uptime_seconds = uptime_ticks / 100.0

        return {
            "estado": "UP",
            "uptime_seconds": uptime_seconds,
            "tiempo_sin_respuesta": 0.0,
            "ultima_respuesta": now.isoformat() + "Z",
            "error": None,
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
