#!/usr/bin/env python
"""Check current migration status"""
import os
import sys
from alembic import command
from alembic.config import Config

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def check_migrations():
    """Display current migration version"""
    alembic_ini = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'alembic.ini'
    )
    alembic_cfg = Config(alembic_ini)
    
    sync_url = settings.DATABASE_URL.replace(
        'postgresql+asyncpg://', 
        'postgresql://'
    )
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    
    command.current(alembic_cfg)


if __name__ == "__main__":
    check_migrations()