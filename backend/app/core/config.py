from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator, Field
import secrets

class Settings(BaseSettings):
    # API
    API_STR: str = Field("/api", env="API_STR")
    
    # Security - БЕЗ ЗНАЧЕНИЙ ПО УМОЛЧАНИЮ для продакшена!
    SECRET_KEY: str = Field(..., env="SECRET_KEY")  # ... означает обязательное поле
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database - берём из переменных окружения
    DATABASE_URL: str = Field(..., env="DATABASE_URL")  # обязательное поле
    
    # Redis
    REDIS_URL: str = Field(..., env="REDIS_URL")  # обязательное поле
    
    # External API
    EXTERNAL_UPDATE_URL: Optional[str] = Field(None, env="EXTERNAL_UPDATE_URL")
    UPDATE_INTERVAL_SECONDS: int = Field(30, env="UPDATE_INTERVAL_SECONDS")
    
    # Worker
    WORKER_CONCURRENCY: int = Field(2, env="WORKER_CONCURRENCY")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = Field([], env="BACKEND_CORS_ORIGINS")
    
    EXTERNAL_UPDATE_URL: Optional[str] = Field(None, env="EXTERNAL_UPDATE_URL")
    EXTERNAL_UPDATE_TOKEN: Optional[str] = Field(None, env="EXTERNAL_UPDATE_TOKEN")
    UPDATE_INTERVAL_SECONDS: int = Field(30, env="UPDATE_INTERVAL_SECONDS", ge=5, le=3600)
    UPDATE_BATCH_SIZE: int = Field(100, env="UPDATE_BATCH_SIZE", ge=1, le=1000)
    UPDATE_TIMEOUT_SECONDS: int = Field(10, env="UPDATE_TIMEOUT_SECONDS")

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Environment
    LOG_LEVEL: str = Field("info", env="LOG_LEVEL")
    ENVIRONMENT: str = Field("production", env="ENVIRONMENT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Важно! Не использовать значения по умолчанию из кода
        validate_default = False

# Создаём экземпляр настроек
# Pydantic сам прочитает переменные окружения
settings = Settings()

# Для отладки (убрать в продакшене)
if settings.ENVIRONMENT == "development":
    print(f"Loaded settings: DATABASE_URL={settings.DATABASE_URL}")
    print(f"REDIS_URL={settings.REDIS_URL}")
    print(f"SECRET_KEY={'*' * 8}")  # не выводим реальный ключ