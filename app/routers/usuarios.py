# app/routers/usuarios.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.router import Router, RouterUser

router = APIRouter(prefix="/usuarios", tags=["Usuarios globales"])


# ---------- Esquemas Pydantic ----------

class GlobalUserBase(BaseModel):
    username: str
    privilege: Optional[int] = None
    permissions: Optional[str] = None


class GlobalUserCreate(GlobalUserBase):
    pass


class GlobalUserUpdate(BaseModel):
    privilege: Optional[int] = None
    permissions: Optional[str] = None


class GlobalUserRead(GlobalUserBase):
    routers: List[str]  # URLs a /routers/<hostname>/usuarios/<username>


# ---------- Helpers internos ----------

async def get_all_routers(db: AsyncSession) -> List[Router]:
    result = await db.execute(
        select(Router).options(selectinload(Router.users))
    )
    routers = result.scalars().unique().all()
    return routers


def build_user_urls(username: str, routers: List[Router]) -> List[str]:
    urls = []
    for r in routers:
        # ¿Ese usuario existe en ese router?
        if any(u.username == username for u in r.users):
            urls.append(f"/routers/{r.hostname}/usuarios/{username}")
    return urls


# ---------- Endpoints ----------

@router.get("/", response_model=List[GlobalUserRead])
async def listar_usuarios_globales(db: AsyncSession = Depends(get_db)):
    """
    Regresa json con los usuarios existentes en la red,
    incluyendo nombre, permisos y dispositivos donde existe
    (URL a routers donde exista cada usuario).
    """
    routers = await get_all_routers(db)

    # Agrupar por username
    users_dict: Dict[str, Dict] = {}
    for r in routers:
        for u in r.users:
            if u.username not in users_dict:
                users_dict[u.username] = {
                    "username": u.username,
                    "privilege": u.privilege,
                    "permissions": u.permissions,
                    "routers": set(),
                }
            users_dict[u.username]["routers"].add(
                f"/routers/{r.hostname}/usuarios/{u.username}"
            )

    result: List[GlobalUserRead] = []
    for data in users_dict.values():
        result.append(
            GlobalUserRead(
                username=data["username"],
                privilege=data["privilege"],
                permissions=data["permissions"],
                routers=sorted(list(data["routers"])),
            )
        )
    return result


@router.post("/", response_model=GlobalUserRead)
async def crear_usuario_global(
    user_in: GlobalUserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Agregar un nuevo usuario a todos los routers,
    regresar json con la misma info de GET pero solo del usuario agregado.
    """
    routers = await get_all_routers(db)

    # Crear el usuario en cada router (si no existe)
    for r in routers:
        existing = next(
            (u for u in r.users if u.username == user_in.username),
            None,
        )
        if existing:
            # Ya existe en ese router: lo dejamos igual
            continue

        new_user = RouterUser(
            username=user_in.username,
            privilege=user_in.privilege,
            permissions=user_in.permissions,
            router_id=r.id,
        )
        db.add(new_user)
        r.users.append(new_user)

        # Aquí podrías llamar a SSH para configurarlo en el router real
        # (pseudocódigo):
        # await ssh_create_user_on_router(
        #     r.ip_admin,
        #     user_in.username,
        #     user_in.privilege,
        #     user_in.permissions,
        # )

    await db.commit()

    urls = build_user_urls(user_in.username, routers)
    return GlobalUserRead(
        username=user_in.username,
        privilege=user_in.privilege,
        permissions=user_in.permissions,
        routers=sorted(urls),
    )


@router.put("/{username}", response_model=GlobalUserRead)
async def actualizar_usuario_global(
    username: str,
    user_in: GlobalUserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Actualizar un usuario en todos los routers,
    regresar json con la misma info de GET pero del usuario actualizado.
    """
    routers = await get_all_routers(db)

    # Buscar el usuario en todos los routers
    usuarios_en_red: List[RouterUser] = []
    for r in routers:
        for u in r.users:
            if u.username == username:
                usuarios_en_red.append(u)

    if not usuarios_en_red:
        raise HTTPException(status_code=404, detail="Usuario no existe en la red")

    # Actualizar datos
    for u in usuarios_en_red:
        if user_in.privilege is not None:
            u.privilege = user_in.privilege
        if user_in.permissions is not None:
            u.permissions = user_in.permissions

        # Aquí iría la actualización por SSH en el router real
        # await ssh_update_user_on_router(...)

    await db.commit()

    # Para la respuesta usamos el primer registro como referencia
    ref = usuarios_en_red[0]
    urls = build_user_urls(ref.username, routers)
    return GlobalUserRead(
        username=ref.username,
        privilege=ref.privilege,
        permissions=ref.permissions,
        routers=sorted(urls),
    )


@router.delete("/{username}", response_model=GlobalUserRead)
async def eliminar_usuario_global(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Eliminar usuario común a todos los routers,
    regresar json con la misma información de GET, pero del usuario eliminado.
    """
    routers = await get_all_routers(db)

    usuarios_en_red: List[RouterUser] = []
    for r in routers:
        for u in r.users:
            if u.username == username:
                usuarios_en_red.append(u)

    if not usuarios_en_red:
        raise HTTPException(status_code=404, detail="Usuario no existe en la red")

    # Guardamos info antes de borrar para la respuesta
    ref = usuarios_en_red[0]
    urls = build_user_urls(ref.username, routers)

    # Borrar de todos los routers
    for u in usuarios_en_red:
        await db.delete(u)
        # Aquí iría la eliminación por SSH:
        # await ssh_delete_user_on_router(...)

    await db.commit()

    return GlobalUserRead(
        username=ref.username,
        privilege=ref.privilege,
        permissions=ref.permissions,
        routers=sorted(urls),
    )



