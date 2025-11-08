# Multi-stage build for ForexFactory Calendar Scraper
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (Chromium + required libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libnss3 \
    lsb-release \
    wget \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY jobs/ jobs/
COPY migrations/ migrations/
COPY .env.example .env.example

# Create necessary directories
RUN mkdir -p csv_output logs

# Set environment variables for headless operation
ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    GITHUB_ACTIONS=true

# Default command (can be overridden)
CMD ["python", "jobs/realtime_15min.py"]
