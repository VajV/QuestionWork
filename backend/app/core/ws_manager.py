"""WebSocket connection manager.

Tracks active WS connections by key (user_id or quest_id) for graceful
shutdown. Individual endpoint handlers manage their own Redis PubSub
subscriptions.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """Registry for active WebSocket connections.

    Keys are arbitrary strings — use user_id for notification connections
    and "chat:{quest_id}" for chat connections.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, key: str, *, accept: bool = True) -> None:
        """Accept a WebSocket and register it under *key*."""
        if accept:
            await ws.accept()
        self._connections[key].add(ws)
        logger.debug("WS connected: key=%s total=%d", key, len(self._connections[key]))

    def disconnect(self, ws: WebSocket, key: str) -> None:
        """Remove a WebSocket from the registry."""
        self._connections[key].discard(ws)
        if not self._connections[key]:
            del self._connections[key]
        logger.debug("WS disconnected: key=%s", key)

    def connection_count(self, key: str) -> int:
        return len(self._connections.get(key, set()))

    async def close_all(self) -> None:
        """Close every connection — called in lifespan shutdown."""
        for key, conns in list(self._connections.items()):
            for ws in list(conns):
                try:
                    await ws.close(1001)
                except Exception:
                    pass
        self._connections.clear()
        logger.info("All WS connections closed")


# Module-level singleton used by endpoints
ws_manager = WSManager()
