from __future__ import annotations

import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .db import SessionLocal
from .frm_client import FRMClient, FRMConnection
from .repository import load_connection_config


@dataclass
class SnapshotState:
    data: dict[str, Any] = field(
        default_factory=lambda: {
            "session_info": None,
            "players": [],
            "factory": [],
            "power": [],
            "power_usage": [],
            "switches": [],
            "map_markers": [],
            "prod_stats": [],
        }
    )
    history: dict[str, deque] = field(
        default_factory=lambda: {
            "power": deque(maxlen=48),
            "production": deque(maxlen=48),
        }
    )
    status: str = "idle"
    last_error: str | None = None
    last_refresh_at: datetime | None = None


class SnapshotService:
    def __init__(self, client: FRMClient) -> None:
        self.client = client
        self.state = SnapshotState()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    def get_state(self) -> SnapshotState:
        snapshot = SnapshotState()
        snapshot.data = deepcopy(self.state.data)
        snapshot.history = {
            "power": deque(self.state.history["power"], maxlen=48),
            "production": deque(self.state.history["production"], maxlen=48),
        }
        snapshot.status = self.state.status
        snapshot.last_error = self.state.last_error
        snapshot.last_refresh_at = self.state.last_refresh_at
        return snapshot

    async def refresh_now(self) -> None:
        async with self._lock:
            await self._refresh_locked()

    async def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                async with self._lock:
                    await self._refresh_locked()
            except Exception as error:
                self.state.status = "error"
                self.state.last_error = str(error)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_seconds())
            except asyncio.TimeoutError:
                continue
            if self._stop.is_set():
                break

    def _poll_interval_seconds(self) -> float:
        with SessionLocal() as session:
            return max(load_connection_config(session).refresh_seconds, 5)

    async def _refresh_locked(self) -> None:
        with SessionLocal() as session:
            config = load_connection_config(session)
            if not config.frm_base_url.strip():
                self.state.status = "idle"
                self.state.last_error = "FRM base URL is not configured."
                return
            connection = FRMConnection(base_url=config.frm_base_url, token=config.frm_token)

        payload = await self.client.refresh_snapshot(connection)
        self.state.data = payload
        self.state.status = "online"
        self.state.last_error = None
        self.state.last_refresh_at = datetime.utcnow()
        self._append_history(payload)

    def _append_history(self, payload: dict[str, Any]) -> None:
        power = payload.get("power", [])
        prod_stats = payload.get("prod_stats", [])
        self.state.history["power"].append(
            {
                "at": datetime.utcnow().isoformat(),
                "production": sum(float(circuit.get("PowerProduction", 0) or 0) for circuit in power),
                "consumption": sum(float(circuit.get("PowerConsumed", 0) or 0) for circuit in power),
                "capacity": sum(float(circuit.get("PowerCapacity", 0) or 0) for circuit in power),
                "battery_min": min((float(circuit.get("BatteryPercent", 0) or 0) for circuit in power), default=0.0),
            }
        )
        self.state.history["production"].append(
            {
                "at": datetime.utcnow().isoformat(),
                "current": sum(float(item.get("CurrentProd", 0) or 0) for item in prod_stats),
                "max": sum(float(item.get("MaxProd", 0) or 0) for item in prod_stats),
            }
        )
