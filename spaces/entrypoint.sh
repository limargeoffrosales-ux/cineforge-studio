#!/bin/bash
set -e
mkdir -p /app/media
cd /app/backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd /app/frontend && ./node_modules/.bin/next start -p 3000 &
exec nginx -g 'daemon off;'