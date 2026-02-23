#!/bin/bash
set -e

# Устанавливаем PYTHONPATH
export PYTHONPATH=/app

echo "========================================"
echo "Starting JSON Database API container"
echo "========================================"

# Проверка подключения к PostgreSQL
echo "Waiting for PostgreSQL to be ready..."
python << END
import asyncio
import asyncpg
import time
from app.core.config import settings

async def wait_for_db():
    db_url = settings.DATABASE_URL.replace(
        'postgresql+asyncpg://', 
        'postgresql://'
    )
    
    for i in range(30):
        try:
            conn = await asyncpg.connect(db_url)
            await conn.close()
            print("PostgreSQL is ready")
            return True
        except Exception as e:
            print(f"Waiting for PostgreSQL... ({i+1}/30)")
            time.sleep(1)
    print("PostgreSQL not ready after 30 seconds")
    return False

if __name__ == "__main__":
    success = asyncio.run(wait_for_db())
    if not success:
        exit(1)
END

# Проверка подключения к Redis
echo "Waiting for Redis to be ready..."
python << END
import redis
import time
from app.core.config import settings

def wait_for_redis():
    for i in range(30):
        try:
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            print("Redis is ready")
            return True
        except Exception as e:
            print(f"Waiting for Redis... ({i+1}/30)")
            time.sleep(1)
    print("Redis not ready after 30 seconds")
    return False

if __name__ == "__main__":
    success = wait_for_redis()
    if not success:
        exit(1)
END

# Запуск миграций
echo "Running database migrations..."
python /app/scripts/run_migrations.py

if [ $? -eq 0 ]; then
    echo "Database migrations complete"
else
    echo "Database migrations failed"
    exit 1
fi

# Запуск приложения
echo "Starting FastAPI application..."
echo "========================================"

# Запускаем Uvicorn и воркер параллельно
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4} &
UVICORN_PID=$!

python -m app.worker &
WORKER_PID=$!

echo "Uvicorn started with PID: $UVICORN_PID"
echo "Worker started with PID: $WORKER_PID"

# Функция для остановки всех процессов
cleanup() {
    echo "Shutting down processes..."
    kill $UVICORN_PID $WORKER_PID 2>/dev/null
    wait $UVICORN_PID $WORKER_PID 2>/dev/null
    exit 0
}

# Перехватываем сигналы
trap cleanup SIGTERM SIGINT

# Ждем завершения любого процесса
wait -n

# Если один процесс завершился, убиваем другой и выходим с ошибкой
echo "One of the processes died, shutting down..."
kill $UVICORN_PID $WORKER_PID 2>/dev/null
exit 1