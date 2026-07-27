#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# scripts/deploy-ec2.sh
# Build & start ytNotesMaker on AWS EC2 (run from project root)
# ─────────────────────────────────────────────────────────────────
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== ytNotesMaker EC2 Deploy ==="

# Required files/dirs — Docker bind-mount fails if cookies.txt is missing
mkdir -p oauth_cache
touch cookies.txt

if [ ! -f ".env" ]; then
    echo "Creating .env from backend/.env (if present)..."
    if [ -f "backend/.env" ]; then
        cp backend/.env .env
    else
        cat > .env <<'EOF'
# Optional: Groq free tier — https://console.groq.com/keys
# GROQ_API_KEY=gsk_your_key_here

# Optional: Gemini — https://makersuite.google.com/app/apikey
# GEMINI_API_KEY=AIzaSy_your_key_here
EOF
    fi
    echo "Edit .env and add GROQ_API_KEY or GEMINI_API_KEY for best results."
fi

if [ ! -s "cookies.txt" ]; then
    echo ""
    echo "NOTE: cookies.txt is empty. Transcripts may fail on EC2 datacenter IPs."
    echo "      Export YouTube cookies from your browser (see DEPLOYMENT.md)."
    echo ""
fi

echo "Building and starting containers..."
docker compose up -d --build

echo ""
echo "Waiting for backend..."
sleep 8

echo ""
echo "=== Transcript test (inside container) ==="
docker compose exec -T backend python test_transcript.py \
    "https://www.youtube.com/watch?v=rfscVS0vtbw" || true

echo ""
echo "=== Status ==="
docker compose ps

PUBLIC_IP=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
echo ""
if [ -n "$PUBLIC_IP" ]; then
    echo "App URL:  http://${PUBLIC_IP}"
    echo "Health:   http://${PUBLIC_IP}:5000/api/health"
else
    echo "App URL:  http://<YOUR_EC2_PUBLIC_IP>"
fi
echo ""
echo "Logs:     docker compose logs -f backend"
