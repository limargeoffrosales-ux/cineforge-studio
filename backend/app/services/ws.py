"""WebSocket connection manager. Clients authenticate with ?token= JWT and
subscribe to their project's events (stage updates, render progress, run
completion). Broadcasts from worker threads are marshalled onto each
socket's own event loop via run_coroutine_threadsafe."""
import asyncio
import logging

from fastapi import WebSocket

from ..security import decode_token

log = logging.getLogger("cineforge.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[str, WebSocket] = {}
        self._loops: dict[str, asyncio.AbstractEventLoop] = {}
        self._projects: dict[str, set[str]] = {}  # user_id -> {project_id}

    async def connect(self, ws: WebSocket, token: str, user_id: str) -> None:
        await ws.accept()
        self._conns[user_id] = ws
        self._loops[user_id] = asyncio.get_running_loop()
        self._projects.setdefault(user_id, set())

    async def disconnect(self, user_id: str) -> None:
        self._conns.pop(user_id, None)
        self._loops.pop(user_id, None)
        self._projects.pop(user_id, None)

    def subscribe(self, user_id: str, project_id: str) -> None:
        self._projects.setdefault(user_id, set()).add(project_id)

    def unsubscribe(self, user_id: str, project_id: str) -> None:
        self._projects.get(user_id, set()).discard(project_id)

    def _send(self, user_id: str, message: dict) -> None:
        ws = self._conns.get(user_id)
        loop = self._loops.get(user_id)
        if ws and loop and not ws.client_state.value > 1:
            try:
                fut = asyncio.run_coroutine_threadsafe(ws.send_json(message), loop)
                fut.result(timeout=1.0)
            except Exception:  # noqa: BLE001
                log.debug("ws send failed for %s", user_id)

    def broadcast_project(self, project_id: str, message: dict) -> None:
        for uid, project_ids in self._projects.items():
            if project_id in project_ids:
                self._send(uid, message)


manager = ConnectionManager()
