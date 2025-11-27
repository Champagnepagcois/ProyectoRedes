from pydantic_settings import BaseSettings 

class Settings(BaseSettings):
    APP_NAME: str = "API Redes"
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = "sqlite+aiosqlite:///./redes.db"

    SSH_USERNAME: str = "admin"
    SSH_PASSWORD: str = "n0m3l0"
    SSH_SECRET: str | None = None  
    
    NEW_USER_PASSWORD: str = "Redes2025"

    SNMP_COMMUNITY: str = "REDES"
    SNMP_PORT: int = 161

    class Config:
        env_file = ".env"

settings = Settings()
