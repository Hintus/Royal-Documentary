#!/usr/bin/env python
"""Run database migrations at container startup"""
import os
import sys
import logging
from alembic import command
from alembic.config import Config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrations")

def run_migrations():
    """Run all pending migrations"""
    try:
        logger.info("=" * 60)
        logger.info("Starting database migrations...")
        
        alembic_ini = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')
        alembic_cfg = Config(alembic_ini)
        
        # Устанавливаем синхронный URL
        sync_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        
        # Применяем ВСЕ миграции до последней
        logger.info("Applying all pending migrations...")
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✅ All migrations applied successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Migrations failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migrations()
    if not success:
        sys.exit(1)