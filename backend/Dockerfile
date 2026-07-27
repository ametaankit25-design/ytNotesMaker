# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# Base: python:3.11-slim  (no venv needed inside Docker)
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps: build tools for faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY req.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r req.txt

# Copy source code
COPY . .

# Create output directory for generated PDFs
RUN mkdir -p /app/output

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"

# Run Flask in production mode (no debug)
CMD ["python", "flask_api.py"]
