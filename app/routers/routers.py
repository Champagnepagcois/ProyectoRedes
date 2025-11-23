# app/routers/routers.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.router import Router, Interface, RouterUser

router = APIRouter(prefix="/routers", tags=["Routers"])


# ---------- Esquemas Pydantic ----------

class InterfaceCreate(BaseModel):
    name: str
    ip_address: Optional[str] = None
    mask: Optional[str] = None
    status: Optional[str] = None
    protocol: Optional[str] = None
    neighbor_hostname: Optional[str] = None


class RouterCreate(BaseModel):
    hostname: str
    ip_admin: str
    loopback: Optional[str] = None
    role: Optional[str] = None
    vendor: Optional[str] = None
    os_version: Optional[str] = None
    interfaces: List[InterfaceCreate] = []


class InterfaceRead(InterfaceCreate):
    id: int

    class Config:
        from_attributes = True


class RouterRead(BaseModel):
    id: int
    hostname: str
    ip_admin: str
    loopback: Optional[str]
    role: Optional[str]
    vendor: Optional[str]
    os_version: Optional[str]
    interfaces: List[InterfaceRead] = []

    class Config:
        from_attributes = True


# ---- Usuarios por router ----

class RouterUserBase(BaseModel):
    username: str
    privilege: Optional[int] = None
    permissions: Optional[str] = None


class RouterUserCreate(RouterUserBase):
    pass


class RouterUserUpdate(BaseModel):
    privilege: Optional[int] = None
    permissions: Optional[str] = None


class RouterUserRead(RouterUserBase):
    id: int

    class Config:
        from_attributes = True


# ---------- Endpoints Routers ----------

@router.post("/", response_model=RouterRead)
async def crear_router(router_in: RouterCreate, db: AsyncSession = Depends(get_db)):
    # Verificar hostname único
    result = await db.execute(select(Router).where(Router.hostname == router_in.hostname))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="El router ya existe")

    router = Router(
        hostname=router_in.hostname,
        ip_admin=router_in.ip_admin,
        loopback=router_in.loopback,
        role=router_in.role,
        vendor=router_in.vendor,
        os_version=router_in.os_version,
    )

    for iface_in in router_in.interfaces:
        iface = Interface(
            name=iface_in.name,
            ip_address=iface_in.ip_address,
            mask=iface_in.mask,
            status=iface_in.status,
            protocol=iface_in.protocol,
            neighbor_hostname=iface_in.neighbor_hostname,
            router=router,
        )
        db.add(iface)

    db.add(router)
    await db.commit()
    await db.refresh(router)
    return router


@router.get("/", response_model=List[RouterRead])
async def listar_routers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Router).options(selectinload(Router.interfaces))
    )
    routers = result.scalars().unique().all()
    return routers


@router.get("/{hostname}", response_model=RouterRead)
async def detalle_router(hostname: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Router)
        .options(selectinload(Router.interfaces))
        .where(Router.hostname == hostname)
    )
    router = result.scalars().unique().one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    return router


# ---------- NUEVO: /routers/{hostname}/interfaces ----------

@router.get("/{hostname}/interfaces", response_model=List[InterfaceRead])
async def interfaces_por_router(hostname: str, db: AsyncSession = Depends(get_db)):
    # Buscar el router por hostname
    result = await db.execute(select(Router).where(Router.hostname == hostname))
    router = result.scalar_one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    result_ifaces = await db.execute(
        select(Interface).where(Interface.router_id == router.id)
    )
    interfaces = result_ifaces.scalars().all()
    return interfaces


# ---------- NUEVO: CRUD usuarios por router ----------

# GET /routers/{hostname}/usuarios/
@router.get("/{hostname}/usuarios/", response_model=List[RouterUserRead])
async def listar_usuarios_router(hostname: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Router).where(Router.hostname == hostname))
    router = result.scalar_one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    result_users = await db.execute(
        select(RouterUser).where(RouterUser.router_id == router.id)
    )
    users = result_users.scalars().all()
    return users


# POST /routers/{hostname}/usuarios/
@router.post("/{hostname}/usuarios/", response_model=RouterUserRead)
async def crear_usuario_router(
    hostname: str,
    user_in: RouterUserCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Router).where(Router.hostname == hostname))
    router = result.scalar_one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    # Comprobar si ya existe ese username en ese router
    result_user = await db.execute(
        select(RouterUser).where(
            RouterUser.router_id == router.id,
            RouterUser.username == user_in.username,
        )
    )
    existing = result_user.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya existe en este router")

    user = RouterUser(
        username=user_in.username,
        privilege=user_in.privilege,
        permissions=user_in.permissions,
        router_id=router.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# PUT /routers/{hostname}/usuarios/{username}
@router.put("/{hostname}/usuarios/{username}", response_model=RouterUserRead)
async def actualizar_usuario_router(
    hostname: str,
    username: str,
    user_in: RouterUserUpdate,
    db: AsyncSession = Depends(get_db),
):
    # Buscar router
    result = await db.execute(select(Router).where(Router.hostname == hostname))
    router = result.scalar_one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    # Buscar usuario
    result_user = await db.execute(
        select(RouterUser).where(
            RouterUser.router_id == router.id,
            RouterUser.username == username,
        )
    )
    user = result_user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en este router")

    if user_in.privilege is not None:
        user.privilege = user_in.privilege
    if user_in.permissions is not None:
        user.permissions = user_in.permissions

    await db.commit()
    await db.refresh(user)
    return user


# DELETE /routers/{hostname}/usuarios/{username}
@router.delete("/{hostname}/usuarios/{username}", response_model=RouterUserRead)
async def eliminar_usuario_router(
    hostname: str,
    username: str,
    db: AsyncSession = Depends(get_db),
):
    # Buscar router
    result = await db.execute(select(Router).where(Router.hostname == hostname))
    router = result.scalar_one_or_none()
    if not router:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    # Buscar usuario
    result_user = await db.execute(
        select(RouterUser).where(
            RouterUser.router_id == router.id,
            RouterUser.username == username,
        )
    )
    user = result_user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en este router")

    await db.delete(user)
    await db.commit()
    return user




