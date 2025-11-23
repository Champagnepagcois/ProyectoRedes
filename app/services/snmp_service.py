# app/services/snmp_service.py
import subprocess
from fastapi.concurrency import run_in_threadpool
from app.config import settings


def _snmp_get_sysinfo_sync(host: str) -> dict:
    """
    Obtiene info básica por SNMP usando el comando del sistema `snmpget`:
    - sysName (1.3.6.1.2.1.1.5.0)
    - sysUpTime (1.3.6.1.2.1.1.3.0)
    """

    base_cmd = [
        "snmpget",
        "-v2c",
        "-c",
        settings.SNMP_COMMUNITY,
        host,
    ]

    oids = {
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
    }

    result: dict[str, str] = {}

    for key, oid in oids.items():
        try:
            proc = subprocess.run(
                base_cmd + [oid],
                capture_output=True,
                text=True,
                timeout=3,
            )

            if proc.returncode != 0:
                # Error de SNMP (timeout, comunidad incorrecta, etc.)
                msg = proc.stderr.strip() or proc.stdout.strip()
                result[key] = f"error: {msg or 'snmpget failed'}"
                continue

            # Ejemplo de salida:
            # SNMPv2-MIB::sysName.0 = STRING: R1
            line = proc.stdout.strip()
            # Nos quedamos con la parte después de '=' y luego de ':'
            try:
                after_equals = line.split("=", 1)[1]
                after_colon = after_equals.split(":", 1)[1]
                value = after_colon.strip()
            except Exception:
                value = line

            result[key] = value

        except Exception as e:
            result[key] = f"error: {e}"

    return result


async def snmp_get_sysinfo(host: str) -> dict:
    """Wrapper asíncrono para FastAPI."""
    return await run_in_threadpool(_snmp_get_sysinfo_sync, host)
