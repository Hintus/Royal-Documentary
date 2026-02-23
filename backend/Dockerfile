FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Дать права на запись в alembic/versions
RUN mkdir -p /app/alembic/versions && \
    chmod -R 777 /app/alembic/versions

USER appuser

ENTRYPOINT ["/entrypoint.sh"]
CMD []