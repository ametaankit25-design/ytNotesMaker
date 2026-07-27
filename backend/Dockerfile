# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# ca-certificates + Node.js (pytubefix). Static ffmpeg (~70MB) instead of apt ffmpeg (~400MB+).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    nodejs \
    && curl -fsSL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" \
      -o /tmp/ffmpeg.tar.xz \
    && tar -xJf /tmp/ffmpeg.tar.xz -C /tmp \
    && mv /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf /tmp/ffmpeg* /var/lib/apt/lists/*

# Install base dependencies with --no-cache-dir to save space
COPY req.txt .
RUN pip install --no-cache-dir --no-cache-dir -r req.txt

# Always upgrade yt-dlp to latest at build time
# (YouTube frequently breaks older versions)
RUN pip install --no-cache-dir --upgrade yt-dlp

COPY . .

RUN mkdir -p /app/output /app/oauth_cache
# Create empty cookies.txt placeholder if not provided at runtime
RUN touch /app/cookies.txt

# Clean up pip cache to save space
RUN pip cache purge

EXPOSE 5000

CMD ["python", "flask_api.py"]
