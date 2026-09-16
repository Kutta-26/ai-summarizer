# ============================================================
# Backend Dockerfile — AI Summarizer Platform
# ============================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime system dependencies: ffmpeg for media processing, curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set container working directory
WORKDIR /app

# Install Python dependencies first for optimal layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY . /app/

# Ensure persistent uploads folder exists with proper permissions
RUN mkdir -p /app/uploads

# Expose backend service port
EXPOSE 8000

# Container healthcheck using FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI application via Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
