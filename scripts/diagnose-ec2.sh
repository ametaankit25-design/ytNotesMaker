#!/bin/bash
# EC2 Diagnostic Script for ytNotesMaker
# This script helps diagnose common issues with the application

set -e

echo "=========================================="
echo "ytNotesMaker EC2 Diagnostic Tool"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check Docker installation
echo "1. Checking Docker installation..."
if command -v docker &> /dev/null; then
    print_status 0 "Docker is installed"
    docker --version
else
    print_status 1 "Docker is not installed"
    exit 1
fi

# Check Docker Compose
echo ""
echo "2. Checking Docker Compose..."
if docker-compose version &> /dev/null; then
    print_status 0 "Docker Compose is available"
    docker-compose version
elif docker compose version &> /dev/null; then
    print_status 0 "Docker Compose is available (newer syntax)"
    docker compose version
else
    print_status 1 "Docker Compose is not available"
    exit 1
fi

# Check running containers
echo ""
echo "3. Checking Docker containers..."
CONTAINERS=$(docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep ytnm)
if [ -n "$CONTAINERS" ]; then
    print_status 0 "ytNotesMaker containers are running"
    echo "$CONTAINERS"
else
    print_status 1 "No ytNotesMaker containers found running"
    echo "Attempting to start containers..."
    docker-compose up -d
fi

# Check container logs
echo ""
echo "4. Checking container logs for errors..."
echo "--- Backend Logs (last 20 lines) ---"
docker-compose logs --tail=20 backend 2>&1 || print_warning "Could not fetch backend logs"

echo ""
echo "--- Frontend Logs (last 20 lines) ---"
docker-compose logs --tail=20 frontend 2>&1 || print_warning "Could not fetch frontend logs"

# Check nginx configuration
echo ""
echo "5. Checking nginx configuration..."
docker-compose exec frontend nginx -t 2>&1 || print_warning "nginx configuration test failed"

# Check backend health
echo ""
echo "6. Checking backend health..."
BACKEND_HEALTH=$(docker-compose exec -T backend curl -s http://localhost:5000/api/health 2>&1 || echo "Failed")
if echo "$BACKEND_HEALTH" | grep -q "ok"; then
    print_status 0 "Backend is healthy"
    echo "$BACKEND_HEALTH"
else
    print_status 1 "Backend health check failed"
    echo "$BACKEND_HEALTH"
fi

# Check frontend health
echo ""
echo "7. Checking frontend health..."
FRONTEND_HEALTH=$(docker-compose exec -T frontend wget -qO- http://localhost/health 2>&1 || echo "Failed")
if echo "$FRONTEND_HEALTH" | grep -q "healthy"; then
    print_status 0 "Frontend is healthy"
else
    print_status 1 "Frontend health check failed"
    echo "$FRONTEND_HEALTH"
fi

# Check cookies.txt
echo ""
echo "8. Checking cookies.txt..."
if [ -f "cookies.txt" ]; then
    FILE_SIZE=$(stat -f%z cookies.txt 2>/dev/null || stat -c%s cookies.txt 2>/dev/null)
    if [ "$FILE_SIZE" -gt 100 ]; then
        print_status 0 "cookies.txt exists and has content ($FILE_SIZE bytes)"
    else
        print_warning "cookies.txt exists but is too small ($FILE_SIZE bytes)"
    fi
else
    print_warning "cookies.txt not found - YouTube transcript extraction may fail"
fi

# Check disk space
echo ""
echo "9. Checking disk space..."
DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    print_status 0 "Disk space is adequate (${DISK_USAGE}% used)"
else
    print_warning "Disk space is high (${DISK_USAGE}% used)"
fi

# Check memory and swap
echo ""
echo "10. Checking memory and swap..."
free -h

# Check port availability
echo ""
echo "11. Checking port availability..."
if netstat -tuln | grep -q ":80 "; then
    print_status 0 "Port 80 is in use"
else
    print_status 1 "Port 80 is not available"
fi

if netstat -tuln | grep -q ":5000 "; then
    print_status 0 "Port 5000 is in use"
else
    print_warning "Port 5000 is not available"
fi

# Test API endpoint
echo ""
echo "12. Testing API endpoint..."
API_TEST=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health 2>&1 || echo "Failed")
if [ "$API_TEST" = "200" ]; then
    print_status 0 "API endpoint is accessible (HTTP $API_TEST)"
else
    print_status 1 "API endpoint returned HTTP $API_TEST"
fi

# Final summary
echo ""
echo "=========================================="
echo "Diagnostic Summary"
echo "=========================================="
echo ""
echo "If you see any RED crosses above, here are some common fixes:"
echo ""
echo "1. Container issues:"
echo "   docker-compose restart"
echo ""
echo "2. Build issues:"
echo "   docker-compose down"
echo "   docker-compose up -d --build"
echo ""
echo "3. Nginx 403 errors:"
echo "   - Check the nginx.conf file has the latest updates"
echo "   - Restart frontend: docker-compose restart frontend"
echo ""
echo "4. Backend errors:"
echo "   - Check logs: docker-compose logs backend"
echo "   - Restart backend: docker-compose restart backend"
echo ""
echo "5. Cookies.txt issues:"
echo "   - Export fresh cookies from browser"
echo "   - Upload to EC2 and restart: docker-compose restart backend"
echo ""
echo "For more help, check the logs:"
echo "   docker-compose logs -f"
echo ""