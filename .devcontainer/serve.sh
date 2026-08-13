#!/bin/bash
# Start the CineForge stack (runs on every container start).
# Uses setsid + detached stdio so the lifecycle shell cannot reap the servers.
set -e
WS=/workspaces/cineforge-studio
export PATH="/home/codespace/nvm/current/bin:$PATH"
mkdir -p "$WS/backend/media"
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true
sleep 1
cd "$WS/backend" && setsid python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 </dev/null > /tmp/cineforge-backend.log 2>&1 &
cd "$WS/frontend" && setsid ./node_modules/.bin/next start -p 3000 </dev/null > /tmp/cineforge-frontend.log 2>&1 &
chmod +x "$WS/.devcontainer/watchdog.sh"
setsid bash "$WS/.devcontainer/watchdog.sh" </dev/null > /tmp/watchdog-run.log 2>&1 &
sleep 8
echo "backend: $(curl -s http://127.0.0.1:8000/healthz || echo DOWN)"
echo "frontend: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000 || echo DOWN)"
