"""
Asymptote — FastAPI WebSocket Server
======================================
Serves the React UI and relays real-time setup updates from Redis pub/sub.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import redis

import config
from engine import redis_store

logger = logging.getLogger("asymptote.server")

# ── WebSocket connection manager ────────────────────────────────────────────

class ConnectionManager:
    """Track active WebSocket clients and broadcast updates."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("Client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("Client disconnected (%d remain)", len(self._connections))

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()

# ── Redis pub/sub listener ──────────────────────────────────────────────────

async def redis_listener() -> None:
    """Subscribe to the ``setups_channel`` and broadcast to WS clients."""
    r = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD,
        decode_responses=True,
    )
    pubsub = r.pubsub()
    pubsub.subscribe("setups_channel")
    logger.info("Redis pub/sub listener started on 'setups_channel'")

    while True:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message and message["type"] == "message":
            try:
                data = json.loads(message["data"])
                await manager.broadcast(data)
            except json.JSONDecodeError:
                pass
        await asyncio.sleep(0.1)


# ── FastAPI app ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the Redis listener on app startup."""
    task = asyncio.create_task(redis_listener())
    yield
    task.cancel()


app = FastAPI(title="Asymptote", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/setups")
async def get_setups():
    """Return all current setups sorted by score (REST fallback)."""
    setups = redis_store.get_all_setups()
    return JSONResponse(content=[
        {**s, "score": sc} for s, sc in setups
    ])


@app.get("/api/candles/{symbol:path}")
async def get_candles(symbol: str):
    """Return cached OHLCV candles for a symbol from Redis."""
    candles = redis_store.get_candles(symbol)
    if candles is None:
        return JSONResponse(content=[], status_code=200)
    return JSONResponse(content=candles)


@app.get("/api/indicators/{symbol:path}")
async def get_indicators(symbol: str):
    """Return cached indicator values for a symbol."""
    ind = redis_store.get_indicators(symbol)
    if ind is None:
        return JSONResponse(content={}, status_code=200)
    return JSONResponse(content=ind)


@app.websocket("/ws/setups")
async def ws_setups(ws: WebSocket):
    """WebSocket endpoint for real-time setup streaming."""
    await manager.connect(ws)

    # Send current state as initial payload
    try:
        setups = redis_store.get_all_setups()
        await ws.send_json({
            "type": "snapshot",
            "data": [{**s, "score": sc} for s, sc in setups],
        })
    except Exception as exc:
        logger.error("Error sending snapshot: %s", exc)

    try:
        while True:
            # Keep connection alive; client can send pings
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Static files (React UI build) ──────────────────────────────────────────
# Uncomment when the ui/dist folder exists:
# app.mount("/", StaticFiles(directory="ui/dist", html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
    )
