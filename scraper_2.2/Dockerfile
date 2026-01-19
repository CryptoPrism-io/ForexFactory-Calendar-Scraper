# Multi-stage build for ForexFactory Calendar Scraper
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (Chromium + Xvfb for virtual display + required libs)
# NOTE: Do NOT install chromium-driver from apt - let undetected-chromedriver download the matching version
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    x11-utils \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libnss3 \
    lsb-release \
    wget \
    xdg-utils \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome binary location for undetected-chromedriver
ENV CHROME_BIN=/usr/bin/chromium

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY jobs/ jobs/
COPY migrations/ migrations/
COPY .env.example .env.example

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p csv_output logs

# Set environment variables for virtual display operation
ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    GITHUB_ACTIONS=true

# Use entrypoint to start Xvfb before running commands
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["python", "jobs/realtime_15min.py"]
