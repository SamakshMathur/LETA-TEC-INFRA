# STAGE 1: Builder
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to leverage Docker cache
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# STAGE 2: Production
FROM python:3.10-slim AS runner

# Set non-interactive for Debian
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime-only dependencies (Tesseract, Poppler, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Pre-download AI models during build (baked into image = zero download at startup)
# bge-large-en-v1.5 ~1.3 GB, ms-marco-MiniLM-L-12-v2 ~22 MB via flashrank
ENV HF_HOME=/root/.cache/huggingface
COPY prebake_models.py /tmp/prebake_models.py
RUN python /tmp/prebake_models.py

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Health Check — 60s start period is enough now that models are baked in
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:${PORT:-8080}/api/health || exit 1

# Production command — sync data files then start uvicorn
RUN chmod +x start.sh
CMD ["bash", "start.sh"]
