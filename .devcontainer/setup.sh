#!/bin/bash
# One-time codespace setup: install backend deps, build frontend.
set -e
export PATH="/home/codespace/nvm/current/bin:$PATH"
echo "==> setup: python version: $(python3 --version)"
pip install --quiet -r /workspaces/cineforge-studio/backend/requirements.txt
cd /workspaces/cineforge-studio/frontend
npm ci --no-audit --no-fund || npm install --no-audit --no-fund
NEXT_TELEMETRY_DISABLED=1 npm run build
echo "==> setup done"