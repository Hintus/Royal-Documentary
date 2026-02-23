import asyncio
import asyncpg
from app.core.config import settings

async def cleanup():
    """Clean all tables except users"""
    conn = await asyncpg.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    
    # Очищаем таблицы в правильном порядке (из-за foreign keys)
    await conn.execute("DELETE FROM refresh_tokens")
    await conn.execute("DELETE FROM document_history")
    await conn.execute("DELETE FROM json_documents")
    # Можно также удалить тестовых пользователей, но осторожно
    # await conn.execute("DELETE FROM users WHERE username LIKE 'testuser_%'")
    
    await conn.close()
    print("Database cleaned")

if __name__ == "__main__":
    asyncio.run(cleanup())