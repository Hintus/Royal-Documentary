import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Импортируем Base и все модели
from app.core.database import Base
from app.models import User, Role, Permission, JsonDocument, DocumentHistory
from app.core.config import settings

# Конфигурация Alembic
config = context.config

# Настройка логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Указываем metadata для автогенерации
target_metadata = Base.metadata

# ПОЛУЧАЕМ URL ИЗ НАСТРОЕК И ЗАМЕНЯЕМ НА СИНХРОННЫЙ ДРАЙВЕР
sync_database_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
config.set_main_option("sqlalchemy.url", sync_database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with sync connection."""
    # Используем синхронный движок для миграций
    from sqlalchemy import create_engine
    
    sync_url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()