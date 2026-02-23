import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.document import JsonDocument

logger = logging.getLogger(__name__)


class ExternalUpdater:
    """Service for periodically updating documents from external URL."""

    def __init__(self):
        self.url = settings.EXTERNAL_UPDATE_URL
        self.token = settings.EXTERNAL_UPDATE_TOKEN
        self.interval = settings.UPDATE_INTERVAL_SECONDS
        self.batch_size = settings.UPDATE_BATCH_SIZE
        self.timeout = aiohttp.ClientTimeout(total=settings.UPDATE_TIMEOUT_SECONDS)
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def fetch_external_data(self) -> Optional[Dict[str, Any]]:
        """Fetch data from external URL."""
        if not self.url:
            logger.warning("EXTERNAL_UPDATE_URL not configured, skipping update")
            return None

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"External API returned status {response.status}")
                        return None
                    
                    data = await response.json()
                    logger.info(f"Fetched external data: {len(str(data))} bytes")
                    return data

        except asyncio.TimeoutError:
            logger.error(f"Timeout while fetching external data from {self.url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching external data: {e}", exc_info=True)
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def update_document(self, db: AsyncSession, document: JsonDocument, external_data: Dict[str, Any]) -> bool:
        """Update single document with external data."""
        try:
            # Получаем текущий контент
            current_content = document.content or {}
            
            # Создаём новое поле с меткой времени
            update_data = {
                "external_update": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": external_data,
                    "source_url": self.url
                }
            }
            
            # Мержим с существующим контентом
            new_content = {**current_content, **update_data}
            
            # Обновляем документ
            document.content = new_content
            document.version += 1
            document.updated_at = func.now()
            
            # Помечаем как изменённое
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(document, "content")
            
            db.add(document)
            await db.flush()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating document {document.id}: {e}")
            return False

    async def update_all_documents(self) -> Dict[str, int]:
        """Update all documents with external data."""
        if not self.url:
            return {"skipped": 0, "updated": 0, "failed": 0, "reason": "URL not configured"}

        logger.info("Starting batch document update from external source")
        
        # Fetch external data once
        external_data = await self.fetch_external_data()
        if not external_data:
            return {"skipped": 0, "updated": 0, "failed": 0, "reason": "Failed to fetch external data"}

        stats = {"updated": 0, "failed": 0, "total": 0}
        
        # Process documents in batches
        async with AsyncSessionLocal() as db:
            try:
                # Get total count
                total_result = await db.execute(select(func.count()).select_from(JsonDocument))
                total = total_result.scalar() or 0
                stats["total"] = total
                
                # Process in batches
                offset = 0
                while offset < total:
                    result = await db.execute(
                        select(JsonDocument)
                        .order_by(JsonDocument.id)
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    documents = result.scalars().all()
                    
                    for document in documents:
                        success = await self.update_document(db, document, external_data)
                        if success:
                            stats["updated"] += 1
                        else:
                            stats["failed"] += 1
                    
                    await db.commit()
                    logger.info(f"Processed batch {offset//self.batch_size + 1}, "
                              f"updated: {stats['updated']}, failed: {stats['failed']}")
                    
                    offset += self.batch_size
                    
            except Exception as e:
                logger.error(f"Error in batch update: {e}", exc_info=True)
                await db.rollback()
                stats["failed"] = total - stats["updated"]
        
        logger.info(f"Batch update completed: {stats}")
        return stats

    async def run_periodic_updates(self):
        """Run periodic updates in background."""
        if not self.url:
            logger.warning("External update URL not configured, periodic updates disabled")
            return

        self.running = True
        logger.info(f"Starting periodic updates every {self.interval} seconds")
        
        while self.running:
            try:
                start_time = datetime.utcnow()
                stats = await self.update_all_documents()
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(f"Update cycle completed in {elapsed:.2f}s: {stats}")
                
                # Ждём следующий цикл
                await asyncio.sleep(self.interval)
                
            except asyncio.CancelledError:
                logger.info("Periodic updates cancelled")
                break
            except Exception as e:
                logger.error(f"Error in update cycle: {e}", exc_info=True)
                await asyncio.sleep(self.interval)

    def start(self):
        """Start the periodic updater."""
        if self._task is not None and not self._task.done():
            logger.warning("Updater already running")
            return
        
        self._task = asyncio.create_task(self.run_periodic_updates())
        logger.info("External updater started")

    async def stop(self):
        """Stop the periodic updater."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("External updater stopped")


# Global instance
updater = ExternalUpdater()