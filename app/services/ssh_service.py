# app/services/ssh_service.py
from netmiko import ConnectHandler
from fastapi.concurrency import run_in_threadpool
from app.config import settings

def _build_device(host: str) -> dict:
    """Construye el diccionario de conexión para Netmiko."""
    return {
        "device_type": "cisco_ios",          # ajusta si usas otro SO
        "host": host,
        "username": settings.SSH_USERNAME,
        "password": settings.SSH_PASSWORD,
        "secret": settings.SSH_SECRET,       # para 'enable', si aplica
    }

def _run_command_sync(host: str, command: str) -> str:
    """Ejecuta un comando por SSH (función síncrona para usar con threadpool)."""
    device = _build_device(host)

    with ConnectHandler(**device) as conn:
        # Si tienes clave de enable, entra al modo privilegiado
        if settings.SSH_SECRET:
            conn.enable()

        output = conn.send_command(command)
    return output

async def run_command(host: str, command: str) -> str:
    """
    Wrapper asíncrono para usar desde FastAPI.
    Netmiko es bloqueante, así que lo mandamos a un threadpool.
    """
    return await run_in_threadpool(_run_command_sync, host, command)
