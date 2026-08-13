#!/usr/bin/env bash
# CineForge AI Studio — one-shot VPS setup + deploy (Ubuntu/Debian).
# Run as root (or with sudo) on a fresh-ish VPS:
#   bash deploy/vps-setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"

echo "==> [1/5] Installing Docker + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y docker-compose-plugin || apt-get install -y docker-compose-v2
fi

echo "==> [2/5] Writing .env"
if [ ! -f .env ]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || openssl rand -hex 32)"
  cp deploy/.env.example .env
  sed -i "s/^JWT_SECRET=.*/JWT_SECRET=${SECRET}/" .env
  echo "    generated JWT_SECRET into .env"
fi

echo "==> [3/5] Building images (first run downloads base images — be patient)"
docker compose build

echo "==> [4/5] Starting stack"
docker compose up -d

echo "==> [5/5] Waiting for health"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    echo "    backend healthy"
    break
  fi
  sleep 2
done

IP="$(curl -fsS -4 ifconfig.me 2>/dev/null || echo 'your-server-ip')"
echo
echo "============================================================"
echo " CineForge AI Studio is UP"
echo "   Studio   : http://${IP}:3000"
echo "   API      : http://${IP}:8000/healthz"
echo "   Demo user: demo@cineforge.ai / cineforge123"
echo " Logs      : docker compose logs -f"
echo " Update    : git pull && docker compose up -d --build"
echo "============================================================"
