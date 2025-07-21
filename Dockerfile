FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create download directory
RUN mkdir -p download

# Environment variables with defaults
ENV PYTHONUNBUFFERED=1
ENV BOT_TOKEN=""
ENV JM_RETRY_TIMES=2
ENV JM_TIMEOUT=15
ENV ENABLE_ZIP_ARCHIVE=true
ENV ZIP_THRESHOLD=5
ENV ENABLE_STORAGE_MANAGEMENT=true
ENV MAX_STORAGE_SIZE_GB=2.0
ENV KEEP_DAYS=7
ENV CLEANUP_INTERVAL_HOURS=6
ENV CACHE_DB_PATH=download/cache.json
ENV SHOW_DOWNLOAD_PROGRESS=true
ENV PROGRESS_UPDATE_INTERVAL=5
# Concurrency settings
ENV MAX_CONCURRENT_DOWNLOADS=2
ENV MAX_CONCURRENT_UPLOADS=3
ENV THREAD_POOL_SIZE=4

# Run the application
CMD ["python", "main.py"]