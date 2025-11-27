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

    transport = paramiko.Transport((host, 22))

    sec_opts = transport.get_security_options()

    try:
        sec_opts.kex = ["diffie-hellman-group1-sha1"]
    except Exception as e:
        print("Error al configurar KEX en Paramiko:", e)

    transport.connect(username=USER, password=PWD)

    session = transport.open_session()
    session.exec_command(command)

    output = session.recv(65535).decode(errors="ignore")

    session.close()
    transport.close()

    return output


async def run_command(host: str, command: str) -> str:
    """
    Wrapper asíncrono para usar desde FastAPI.
    Lanza la función bloqueante en un threadpool.
    """
    return await run_in_threadpool(_run_command_sync, host, command)


def _push_config_sync(host: str, config_commands: list[str]) -> str:
    """
    Abre sesión SSH y ejecuta una serie de comandos de configuración:
    entra a 'conf t', aplica los comandos, sale y guarda config (wr).
    """
    USER = settings.SSH_USERNAME
    PWD = settings.SSH_PASSWORD

    transport = paramiko.Transport((host, 22))

    sec_opts = transport.get_security_options()
    try:
        sec_opts.kex = ["diffie-hellman-group1-sha1"]
    except Exception as e:
        print("Error al configurar KEX en Paramiko:", e)

    transport.connect(username=USER, password=PWD)

    session = transport.open_session()

    # armamos el "script" de configuración
    cmds = ["configure terminal"]
    cmds.extend(config_commands)
    cmds.extend(["end", "write memory"])

    full_cmd = "\n".join(cmds) + "\n"
    session.exec_command(full_cmd)

    output = session.recv(65535).decode(errors="ignore")

    session.close()
    transport.close()

    return output


async def push_config(host: str, config_commands: list[str]) -> str:
    """
    Versión asíncrona para usar desde FastAPI.
    """
    return await run_in_threadpool(_push_config_sync, host, config_commands)



async def create_user_on_router(
    host: str,
    username: str,
    privilege: int | None,
    password: str | None = None,
):
    """
    Crea (o sobreescribe) un usuario en el router IOS.
    """
    if privilege is None:
        privilege = 1
    if password is None:
        password = settings.NEW_USER_PASSWORD

    cmd = f"username {username} privilege {privilege} secret {password}"
    return await push_config(host, [cmd])


async def update_user_on_router(
    host: str,
    username: str,
    privilege: int | None = None,
    password: str | None = None,
):
    """
    Actualiza privilegio y/o contraseña de un usuario.
    En IOS, re-ejecutar 'username ...' lo sobrescribe.
    """
    if privilege is None:
        privilege = 1
    if password is None:
        password = settings.NEW_USER_PASSWORD

    cmd = f"username {username} privilege {privilege} secret {password}"
    return await push_config(host, [cmd])


async def delete_user_on_router(host: str, username: str):
    """
    Elimina usuario del router.
    """
    cmd = f"no username {username}"
    return await push_config(host, [cmd])
