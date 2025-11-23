# app/models/router.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base


class Router(Base):
    __tablename__ = "routers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, index=True, nullable=False)
    ip_admin = Column(String, nullable=False)
    loopback = Column(String, nullable=True)
    role = Column(String, nullable=True)
    vendor = Column(String, nullable=True)
    os_version = Column(String, nullable=True)

    interfaces = relationship(
        "Interface",
        back_populates="router",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    users = relationship(
        "RouterUser",
        back_populates="router",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Interface(Base):
    __tablename__ = "interfaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    mask = Column(String, nullable=True)
    status = Column(String, nullable=True)
    protocol = Column(String, nullable=True)

    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    router = relationship("Router", back_populates="interfaces")

    neighbor_hostname = Column(String, nullable=True)


class RouterUser(Base):
    __tablename__ = "router_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    privilege = Column(Integer, nullable=True)        # nivel 1–15
    permissions = Column(String, nullable=True)       # descripción de permisos

    router_id = Column(Integer, ForeignKey("routers.id"), nullable=False)
    router = relationship("Router", back_populates="users")




