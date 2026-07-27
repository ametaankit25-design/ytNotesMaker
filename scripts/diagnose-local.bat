@echo off
REM Windows Diagnostic Script for ytNotesMaker
REM This script helps diagnose common issues with the application locally

echo ==========================================
echo ytNotesMaker Local Diagnostic Tool
echo ==========================================
echo.

REM Check Docker installation
echo 1. Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Docker is installed
    docker --version
) else (
    echo [ERROR] Docker is not installed
    exit /b 1
)

echo.

REM Check Docker Compose
echo 2. Checking Docker Compose...
docker-compose version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Docker Compose is available
    docker-compose version
) else (
    echo [ERROR] Docker Compose is not available
    exit /b 1
)

echo.

REM Check running containers
echo 3. Checking Docker containers...
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr ytnm >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] ytNotesMaker containers are running
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr ytnm
) else (
    echo [WARNING] No ytNotesMaker containers found running
    echo Attempting to start containers...
    docker-compose up -d
)

echo.

REM Check container logs
echo 4. Checking container logs for errors...
echo --- Backend Logs (last 20 lines) ---
docker-compose logs --tail=20 backend 2>&1

echo.
echo --- Frontend Logs (last 20 lines) ---
docker-compose logs --tail=20 frontend 2>&1

echo.

REM Check nginx configuration
echo 5. Checking nginx configuration...
docker-compose exec frontend nginx -t 2>&1

echo.

REM Check backend health
echo 6. Checking backend health...
docker-compose exec -T backend curl -s http://localhost:5000/api/health 2>&1

echo.

REM Check frontend health
echo 7. Checking frontend health...
docker-compose exec -T frontend wget -qO- http://localhost/health 2>&1

echo.

REM Check cookies.txt
echo 8. Checking cookies.txt...
if exist cookies.txt (
    for %%I in (cookies.txt) do set SIZE=%%~zI
    if !SIZE! gtr 100 (
        echo [OK] cookies.txt exists and has content (!SIZE! bytes)
    ) else (
        echo [WARNING] cookies.txt exists but is too small (!SIZE! bytes)
    )
) else (
    echo [WARNING] cookies.txt not found - YouTube transcript extraction may fail
)

echo.

REM Check disk space
echo 9. Checking disk space...
wmic logicaldisk get name,freespace,size

echo.

REM Test API endpoint
echo 10. Testing API endpoint...
curl -s -o nul -w "%%{http_code}" http://localhost/api/health 2>&1

echo.
echo ==========================================
echo Diagnostic Summary
echo ==========================================
echo.
echo If you see any errors above, here are some common fixes:
echo.
echo 1. Container issues:
echo    docker-compose restart
echo.
echo 2. Build issues:
echo    docker-compose down
echo    docker-compose up -d --build
echo.
echo 3. Nginx 403 errors:
echo    - Check the nginx.conf file has the latest updates
echo    - Restart frontend: docker-compose restart frontend
echo.
echo 4. Backend errors:
echo    - Check logs: docker-compose logs backend
echo    - Restart backend: docker-compose restart backend
echo.
echo For more help, check the logs:
echo    docker-compose logs -f
echo.
pause