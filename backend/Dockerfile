# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps: build tools for python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        gcc \
        g++ \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

# Copy source code
COPY . .

# Create output directory for generated PDFs
RUN mkdir -p /app/output

EXPOSE 5000

CMD ["python", "flask_api.py"]
