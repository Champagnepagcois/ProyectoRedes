# app/routers/ssh_test.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ssh_service import run_command

router = APIRouter(prefix="/ssh", tags=["SSH"])

class SSHRequest(BaseModel):
    host: str          # IP o hostname del router
    command: str = "show ip interface brief"  # comando por defecto

@router.post("/test")
async def ssh_test(req: SSHRequest):
    """
    Prueba conexión SSH y ejecución de un comando.
    """
    try:
        output = await run_command(req.host, req.command)
        return {
            "host": req.host,
            "command": req.command,
            "output": output,
        }
    except Exception as e:
        # Puedes loguear e en algún lado si quieres
        raise HTTPException(status_code=500, detail=str(e))
