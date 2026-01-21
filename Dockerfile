# E-Claim Downloader & Import System
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies (include mysql-client for both DB support)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    default-mysql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
# Note: config/ already exists from COPY, so we don't create it
# data/ is for user settings persistence (settings.json will be stored here)
RUN mkdir -p logs downloads backups data && \
    chmod -R 755 /app

# Set permissions for scripts
RUN chmod +x eclaim_import.py eclaim_downloader_http.py bulk_downloader.py 2>/dev/null || true && \
    chmod +x docker-entrypoint.sh

# Expose Flask port
EXPOSE 5001

# Environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Bangkok
ENV APP_ROOT=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5001/ || exit 1

# Use entrypoint script for migrations
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command: run Flask app
CMD ["python", "app.py"]
