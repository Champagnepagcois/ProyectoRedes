# app/services/ssh_service.py
import paramiko
from fastapi.concurrency import run_in_threadpool
from app.config import settings


def _run_command_sync(host: str, command: str) -> str:
    """
    Ejecuta un comando por SSH usando Paramiko (versión síncrona).
    Esta función se manda a un threadpool desde FastAPI.
    """

    USER = settings.SSH_USERNAME
    PWD = settings.SSH_PASSWORD

    # 1. Crear el objeto Transport apuntando al puerto 22
    transport = paramiko.Transport((host, 22))

    # 2. Forzar el algoritmo de intercambio de claves compatible con IOS viejo
    sec_opts = transport.get_security_options()

    # Ojo: si tu versión de Paramiko soporta group1, esto funciona.
    # (Ya vimos que en tu caso sí funciona con el test que hiciste)
    try:
        sec_opts.kex = ["diffie-hellman-group1-sha1"]
    except Exception as e:
        # Si por alguna razón no lo acepta, al menos logueamos
        print("Error al configurar KEX en Paramiko:", e)

    # 3. Conectar con usuario y contraseña
    transport.connect(username=USER, password=PWD)

    # 4. Abrir sesión y ejecutar el comando
    session = transport.open_session()
    session.exec_command(command)

    output = session.recv(65535).decode(errors="ignore")

    # 5. Cerrar sesión y transporte
    session.close()
    transport.close()

    return output


async def run_command(host: str, command: str) -> str:
    """
    Wrapper asíncrono para usar desde FastAPI.
    Lanza la función bloqueante en un threadpool.
    """
    return await run_in_threadpool(_run_command_sync, host, command)
