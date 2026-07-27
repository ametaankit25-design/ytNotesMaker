#!/bin/bash

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 YT Notes Maker - Docker Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Required for docker-compose bind mount (EC2 / fresh clone)
mkdir -p oauth_cache
touch cookies.txt

# Check if .env exists and has API key
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found!"
    echo "Creating .env file..."
    cp backend/.env .env
fi

# Check for API keys
if ! grep -q "GROQ_API_KEY=gsk_" .env && \
   ! grep -q "GEMINI_API_KEY=AIza" .env && \
   ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "⚠️  WARNING: No API key found in .env file!"
    echo ""
    echo "The app will use local Ollama which may generate generic content."
    echo ""
    echo "For best results, add an API key to .env file:"
    echo "  GROQ_API_KEY=gsk_your_key_here"
    echo ""
    echo "Get free API key: https://console.groq.com/keys"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled. Please add API key to .env and run again."
        exit 1
    fi
else
    echo "✅ API key found in .env"
fi

echo ""
echo "Building and starting containers..."
echo ""

docker-compose up --build -d

if [ $? -eq 0 ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Application Started Successfully!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Services:"
    echo "  🌐 Frontend:  http://localhost"
    echo "  🔌 Backend:   http://localhost:5000"
    echo "  ❤️  Health:    http://localhost:5000/api/health"
    echo ""
    echo "View logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "Stop services:"
    echo "  docker-compose down"
    echo ""
    
    sleep 3
    
    echo "Checking backend status..."
    docker-compose logs backend | grep "LLM Engine" | head -1
    
else
    echo ""
    echo "❌ Failed to start containers"
    echo ""
    echo "Check logs with:"
    echo "  docker-compose logs"
fi
