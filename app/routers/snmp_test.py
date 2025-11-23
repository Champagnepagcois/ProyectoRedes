# app/routers/snmp_test.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.snmp_service import snmp_get_sysinfo

router = APIRouter(prefix="/snmp", tags=["SNMP"])

class SNMPRequest(BaseModel):
    host: str  # IP o hostname del router

@router.post("/test")
async def snmp_test(req: SNMPRequest):
    """
    Prueba consulta SNMP básica (sysName y sysUpTime).
    """
    try:
        info = await snmp_get_sysinfo(req.host)
        return {
            "host": req.host,
            "info": info,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
