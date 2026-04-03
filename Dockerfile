# ─── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-liberation \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser (deps installed manually above)
# || true: ignores the harmless EIO __dirlock cleanup error on Docker/Windows
RUN playwright install chromium || true

# Copy source code and profile
COPY src/ ./src/
COPY profile.md .

# Data directory (will be volume-mounted at runtime to persist jobs.duckdb)
RUN mkdir -p /app/data

# Add src/ to Python path so modules import cleanly
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# ─── Runtime ─────────────────────────────────────────────────────────────────
ENTRYPOINT ["python", "/app/src/scheduler.py"]
