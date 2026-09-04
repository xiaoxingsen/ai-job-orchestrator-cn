from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import uuid4


class JsonSocket(Protocol):
    async def send_json(self, message: dict) -> None: ...


class ExtensionBroker:
    def __init__(self) -> None:
        self._socket: JsonSocket | None = None
        self._pending: dict[str, asyncio.Future[object]] = {}
        self._send_lock = asyncio.Lock()
        self._last_risk: dict | None = None

    async def attach(self, socket: JsonSocket) -> None:
        async with self._send_lock:
            self._socket = socket

    async def detach(self, socket: JsonSocket) -> None:
        async with self._send_lock:
            if self._socket is not socket:
                return
            self._socket = None
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("browser extension disconnected"))

    async def send_command(
        self, command_type: str, payload: dict, *, timeout_seconds: float = 30
    ) -> object:
        if self._socket is None:
            raise ConnectionError("browser extension is not connected")
        command_id = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        try:
            async with self._send_lock:
                if self._socket is None:
                    raise ConnectionError("browser extension is not connected")
                await self._socket.send_json(
                    {"command_id": command_id, "type": command_type, "payload": payload}
                )
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        finally:
            self._pending.pop(command_id, None)

    async def handle_message(self, message: dict) -> None:
        if message.get("event") == "risk_stopped" and isinstance(message.get("payload"), dict):
            self._last_risk = message["payload"]
            return
        command_id = message.get("command_id")
        if not isinstance(command_id, str) or "result" not in message:
            return
        future = self._pending.get(command_id)
        if future is not None and not future.done():
            future.set_result(message["result"])

    def status(self) -> dict:
        return {
            "connected": self._socket is not None,
            "pending_commands": len(self._pending),
            "last_risk": self._last_risk,
        }

