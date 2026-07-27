# ─────────────────────────────────────────────────────────────────
# Backend — Flask API + LangGraph + FPDF
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install base dependencies
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

# Always upgrade yt-dlp to latest at build time
# (YouTube frequently breaks older versions)
RUN pip install --no-cache-dir --upgrade yt-dlp

COPY . .

RUN mkdir -p /app/output
# Create empty cookies.txt placeholder if not provided
RUN touch /app/cookies.txt

EXPOSE 5000

CMD ["python", "flask_api.py"]
