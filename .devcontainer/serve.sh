#!/bin/bash
# Start the CineForge stack (runs on every container start).
set -e
WS=/workspaces/cineforge-studio
mkdir -p "$WS/backend/media"
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true
sleep 1
cd "$WS/backend" && nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/cineforge-backend.log 2>&1 &
cd "$WS/frontend" && nohup ./node_modules/.bin/next start -p 3000 > /tmp/cineforge-frontend.log 2>&1 &
sleep 8
echo "backend: $(curl -s http://127.0.0.1:8000/healthz || echo DOWN)"
echo "frontend: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000 || echo DOWN)"