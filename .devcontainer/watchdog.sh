#!/bin/bash
# Self-healing watchdog: keeps the CineForge servers listening on 3000/8000.
# Runs detached from the devcontainer lifecycle (started by serve.sh).
WS=/workspaces/cineforge-studio
while true; do
    sleep 30
    if ! curl -sf -o /dev/null http://127.0.0.1:3000/; then
        echo "$(date -u +%H:%M:%S) FE down — restarting next" >> /tmp/watchdog.log
        pkill -f "next-server" 2>/dev/null || true
        pkill -f "bin/next start" 2>/dev/null || true
        sleep 2
        cd "$WS/frontend" || exit 1
        setsid ./node_modules/.bin/next start -p 3000 </dev/null > /tmp/cineforge-frontend.log 2>&1 &
    fi
    if ! curl -sf -o /dev/null http://127.0.0.1:8000/healthz; then
        echo "$(date -u +%H:%M:%S) BE down — restarting uvicorn" >> /tmp/watchdog.log
        pkill -f "uvicorn app.main" 2>/dev/null || true
        sleep 2
        cd "$WS/backend" || exit 1
        setsid python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 </dev/null > /tmp/cineforge-backend.log 2>&1 &
    fi
done