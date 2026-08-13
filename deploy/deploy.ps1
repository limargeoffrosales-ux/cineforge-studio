# CineForge AI Studio - one-command VPS deploy (Windows PowerShell).
# Pushes this folder to the server via tar+scp, runs deploy/vps-setup.sh,
# then verifies backend /healthz and frontend :3000.
#
# Usage:
#   $env:CINEFORGE_HOST="203.0.113.10"; $env:CINEFORGE_USER="root"
#   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1
#
# First run only - install your SSH key on the server (will prompt for the
# server password once):
#   ssh-keygen -t ed25519 -N "" -f $env:USERPROFILE\.ssh\id_ed25519
#   type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@203.0.113.10 "cat >> ~/.ssh/authorized_keys"
#
# Note: .env, media files and the SQLite DB live on the server / in the
# cineforge_data Docker volume - they are NEVER overwritten by re-deploys.

$ErrorActionPreference = "Stop"

$HOST  = if ($env:CINEFORGE_HOST)  { $env:CINEFORGE_HOST }  else { throw "Set CINEFORGE_HOST (e.g. 203.0.113.10)" }
$USER  = if ($env:CINEFORGE_USER)  { $env:CINEFORGE_USER }  else { "root" }
$PORT  = if ($env:CINEFORGE_PORT)  { $env:CINEFORGE_PORT }  else { "22" }
$KEY   = if ($env:CINEFORGE_KEY)   { $env:CINEFORGE_KEY }   else { "$env:USERPROFILE\.ssh\id_ed25519" }

$REPO  = Split-Path -Parent $PSScriptRoot
$TAR   = "$env:TEMP\cineforge-deploy.tar.gz"
$SSHOPTS = "-i `"$KEY`" -p $PORT -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
$TARGET = "$USER@$HOST"

Write-Host "==> [1/4] Preflight (host=$HOST user=$USER key=$KEY)"
if (-not (Test-Path $KEY)) {
  throw "No SSH key at $KEY. Run: ssh-keygen -t ed25519 -N `"`" -f `"$KEY`"  then install it (see header comments)."
}
ssh $SSHOPTS $TARGET "echo connected" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "SSH connection failed - is the key installed on the server?" }

Write-Host "==> [2/4] Packing project (excluding node_modules/.next/.venv/media/.git)"
tar -czf $TAR -C $REPO --exclude "cineforge/node_modules" --exclude "cineforge/.next" `
  --exclude "cineforge/.venv" --exclude "cineforge/media" --exclude "cineforge/.git" `
  --exclude "cineforge/backend/__pycache__" --exclude "cineforge/backend/tests/__pycache__" `
  --exclude "*.db" --exclude "cineforge/deploy/*.tar.gz" cineforge
if ($LASTEXITCODE -ne 0) { throw "tar failed" }

Write-Host "==> [3/4] Uploading + running vps-setup.sh on server (docker install may take minutes)"
scp $SSHOPTS $TAR "$TARGET:/tmp/cineforge-deploy.tar.gz" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "scp failed" }
ssh $SSHOPTS $TARGET "rm -rf /tmp/cineforge-app && mkdir -p /tmp/cineforge-app && tar -xzf /tmp/cineforge-deploy.tar.gz -C /tmp/cineforge-app && mkdir -p ~/cineforge && cp -rn /tmp/cineforge-app/cineforge/. ~/cineforge/ && cd ~/cineforge && bash deploy/vps-setup.sh"
if ($LASTEXITCODE -ne 0) { throw "remote deploy failed" }

Write-Host "==> [4/4] Verifying deployment"
ssh $SSHOPTS $TARGET "curl -fsS http://127.0.0.1:8000/healthz && echo && curl -fsSo /dev/null -w 'frontend :3000 -> HTTP %{http_code}`n' http://127.0.0.1:3000/"
if ($LASTEXITCODE -ne 0) { Write-Host "WARNING: backend or frontend not responding yet - check 'ssh $TARGET docker compose -f ~/cineforge/docker-compose.yml logs -f'" -ForegroundColor Yellow }

Write-Host "============================================================"
Write-Host " CineForge AI Studio deployed to $TARGET"
Write-Host "   Studio   : http://$HOST`:3000"
Write-Host "   API      : http://$HOST`:8000/healthz"
Write-Host "   Demo user: demo@cineforge.ai / cineforge123"
Write-Host " Update    : re-run this script"
Write-Host "============================================================"
