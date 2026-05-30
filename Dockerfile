# Multi-stage build for Pigeon Guard Turret
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py ./
COPY app/ ./app/

# Create non-root user for security
RUN useradd -m -u 1000 turret && chown -R turret:turret /app
USER turret

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GPIOZERO_PIN_FACTORY=mock

# Run the application
CMD ["python", "main.py"]
