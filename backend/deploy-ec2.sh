#!/bin/bash

# YT Notes Maker - EC2 Docker Deployment Script

set -e

echo "🚀 Deploying YT Notes Maker Backend on EC2"
echo "==========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo "Creating .env file..."
    echo "GROQ_API_KEY=your_groq_api_key_here" > .env
    echo "PORT=5000" >> .env
    echo -e "${YELLOW}Please edit .env file with your actual GROQ_API_KEY${NC}"
    exit 1
fi

# Stop and remove existing container
echo "🛑 Stopping existing container..."
docker stop ytnotesmaker 2>/dev/null || true
docker rm ytnotesmaker 2>/dev/null || true

# Build new image
echo "🔨 Building Docker image..."
docker build -t ytnotesmaker-backend .

# Run new container
echo "🚀 Starting container..."
docker run -d \
  --name ytnotesmaker \
  -p 5000:5000 \
  --env-file .env \
  --restart unless-stopped \
  ytnotesmaker-backend

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 5

# Check if running
if docker ps | grep -q ytnotesmaker; then
    echo -e "${GREEN}✅ Container is running!${NC}"
    echo ""
    echo "📊 Container Status:"
    docker ps | grep ytnotesmaker
    echo ""
    echo "📝 Recent Logs:"
    docker logs --tail 20 ytnotesmaker
    echo ""
    echo -e "${GREEN}🎉 Deployment successful!${NC}"
    echo ""
    echo "Test it:"
    echo "  curl http://localhost:5000/api/health"
    echo ""
    echo "View logs:"
    echo "  docker logs -f ytnotesmaker"
else
    echo "❌ Container failed to start!"
    echo "Check logs:"
    docker logs ytnotesmaker
    exit 1
fi
