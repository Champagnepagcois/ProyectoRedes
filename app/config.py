# app/config.py
from pydantic_settings import BaseSettings  # ya lo tenías así

class Settings(BaseSettings):
    APP_NAME: str = "API Redes"
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = "sqlite+aiosqlite:///./redes.db"

    # 🔐 Credenciales para routers (modifícalas a las tuyas)
    SSH_USERNAME: str = "cisco"
    SSH_PASSWORD: str = "cisco"
    SSH_SECRET: str | None = None  # si usas enable, pon la clave aquí

    SNMP_COMMUNITY: str = "public"
    SNMP_PORT: int = 161

    class Config:
        env_file = ".env"

settings = Settings()
