# app/routers/ping.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/ping")
async def ping():
    return {"message": "pong"}
