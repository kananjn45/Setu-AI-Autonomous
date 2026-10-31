# Production Dockerfile for SETU — Autonomous Operations Teammate
# Paytm Build for India AI Hackathon | Track 3: Autonomous AI Teammates
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose HTTP / WebSocket port
EXPOSE 8080

# Run FastAPI app with Uvicorn (WebSockets supported)
CMD ["sh", "-c", "uvicorn settle_ai.server:app --host 0.0.0.0 --port ${PORT}"]

