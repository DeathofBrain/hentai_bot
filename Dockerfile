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

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose any necessary ports (if needed)
# EXPOSE 8080

# Run the application
CMD ["python", "main.py"]