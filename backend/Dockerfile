# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# ca-certificates + Node.js (pytubefix botGuard / PO token on EC2 datacenter IPs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install base dependencies
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

# Always upgrade yt-dlp to latest at build time
# (YouTube frequently breaks older versions)
RUN pip install --no-cache-dir --upgrade yt-dlp

COPY . .

RUN mkdir -p /app/output /app/oauth_cache
# Create empty cookies.txt placeholder if not provided at runtime
RUN touch /app/cookies.txt

EXPOSE 5000

CMD ["python", "flask_api.py"]
