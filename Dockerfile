# AeroPulse-X Digital Twin — Container Deployment
FROM python:3.11-slim

# System environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies (curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (lightweight CPU PyTorch for container)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application source code and trained AI models
COPY . .

# Expose FastAPI & WebSocket port
EXPOSE 8000

# Health check to ensure application is responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start AeroPulse-X production server
CMD ["python", "run.py"]
