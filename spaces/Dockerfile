# CineForge AI Studio — Hugging Face Spaces single-container image (CPU basic, free).
# Routing: nginx :7860 -> next.js :3000 ; next rewrites /api/backend/* -> FastAPI :8000
# Build stage uses node:20-bookworm-slim (glibc) so node_modules match the glibc runtime.

FROM node:20-bookworm-slim AS webbuild
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MEDIA_DIR=/app/media \
    DATABASE_URL=sqlite:////app/cineforge.db

RUN apt-get update && apt-get install -y --no-install-recommends nginx-light bash \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY backend/tests ./backend/tests

COPY --from=webbuild /usr/local/bin/node /usr/local/bin/node
COPY --from=webbuild /app/.next ./frontend/.next
COPY --from=webbuild /app/node_modules ./frontend/node_modules
COPY --from=webbuild /app/package.json ./frontend/package.json
COPY --from=webbuild /app/next.config.js ./frontend/next.config.js

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 7860
CMD ["/entrypoint.sh"]