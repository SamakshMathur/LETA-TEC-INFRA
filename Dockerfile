# --- Stage 1: Build the React Frontend ---
FROM node:20 AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .
RUN npm run build

# --- Stage 2: Build the FastAPI Backend ---
FROM python:3.10-slim
WORKDIR /app

# Install system dependencies (Tesseract OCR, Poppler, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies from the backend directory
COPY rag-backend/requirements.txt ./rag-backend/
RUN pip install --no-cache-dir -r rag-backend/requirements.txt

# Copy the backend code
COPY rag-backend/ ./rag-backend/

# Copy the built frontend from Stage 1 directly into the backed's expected relative path
# Fast API expects it at __file__.parent.parent.parent / "frontend" / "dist"
COPY --from=frontend-builder /app/frontend/dist /app/rag-backend/frontend/dist

# Expose the port
EXPOSE 8000

ENV PYTHONPATH=/app/rag-backend

# Note: Adjusting the CWD to rag-backend so relative paths (like 'data/generated_reports') resolve correctly
WORKDIR /app/rag-backend

CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
