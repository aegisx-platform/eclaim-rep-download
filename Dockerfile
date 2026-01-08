# E-Claim Downloader & Import System
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
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
RUN mkdir -p logs downloads config backups && \
    chmod -R 755 /app

# Set permissions for scripts
RUN chmod +x eclaim_import.py eclaim_downloader_http.py bulk_downloader.py 2>/dev/null || true

# Expose Flask port
EXPOSE 5001

# Environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Bangkok

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5001/ || exit 1

# Default command: run Flask app
CMD ["python", "app.py"]
