#!/usr/bin/env bash
# CineForge AI Studio — end-to-end API smoke test (login → image2video → poll → final MP4).
# Usage: bash deploy/smoke.sh [BASE_URL] [SEED_IMAGE] [EMAIL] [PASSWORD]
#   BASE_URL     default http://127.0.0.1:8000
#   SEED_IMAGE   default deploy/smoke/seed.png
#   EMAIL/PASS   default demo@cineforge.ai / cineforge123
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
SEED="${2:-$(dirname "$0")/smoke/seed.png}"
EMAIL="${3:-demo@cineforge.ai}"
PASS="${4:-cineforge123}"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PY=python ;; # Git Bash on Windows -> venv python.exe
  *) if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi ;;
esac
json() { "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d$1)"; }

echo "==> smoke: login as $EMAIL"
TOKEN="$(curl -fsS -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | json "['access_token']")"

echo "==> smoke: upload seed image -> /video/image2video"
JOB="$(curl -fsS -X POST "$BASE/video/image2video" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$SEED" \
  -F "prompt=gentle slow zoom with drifting clouds" \
  -F "duration_s=4" \
  -F "movement=auto" | json "['job_id']")"
echo "    job: $JOB"

echo "==> smoke: poll /render/jobs until done"
STATUS="queued"
ROW=""
for i in $(seq 1 90); do
  ROW="$(curl -fsS "$BASE/render/jobs" -H "Authorization: Bearer $TOKEN" | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(json.dumps([j for j in d if j['id']=='$JOB'][0]))")"
  STATUS="$(printf '%s' "$ROW" | json "['status']")"
  case "$STATUS" in
    completed) break ;;
    failed) echo "SMOKE FAIL: job $JOB failed"; printf '%s' "$ROW" | json "['error']"; exit 1 ;;
  esac
  sleep 2
done
[ "$STATUS" = "completed" ] || { echo "SMOKE FAIL: job $JOB still $STATUS after 180s"; exit 1; }

FINAL="$(printf '%s' "$ROW" | json "['final_url']")"
SIZE="$(curl -fsS -o /dev/null -w '%{size_download}' "$BASE$FINAL")"
[ -n "$SIZE" ] && [ "$SIZE" -gt 10000 ] || { echo "SMOKE FAIL: final too small ($SIZE bytes)"; exit 1; }

echo "SMOKE OK: job $JOB -> $FINAL ($SIZE bytes)"
