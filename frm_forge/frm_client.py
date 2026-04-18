from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

READ_ENDPOINTS = {
    "session_info": "getSessionInfo",
    "players": "getPlayer",
    "factory": "getFactory",
    "power": "getPower",
    "power_usage": "getPowerUsage",
    "switches": "getSwitches",
    "map_markers": "getMapMarkers",
    "prod_stats": "getProdStats",
}


@dataclass(slots=True)
class FRMConnection:
    base_url: str
    token: str = ""

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


class FRMClient:
    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-FRM-Authorization"] = token
            headers["Authorization"] = token
        return headers

    async def read_endpoint(self, connection: FRMConnection, endpoint_name: str) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{connection.normalized_base_url}/{endpoint_name}",
                headers=self._headers(connection.token),
            )
            response.raise_for_status()
            return response.json()

    async def refresh_snapshot(self, connection: FRMConnection) -> dict[str, Any]:
        results: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for key, endpoint in READ_ENDPOINTS.items():
                response = await client.get(
                    f"{connection.normalized_base_url}/{endpoint}",
                    headers=self._headers(connection.token),
                )
                response.raise_for_status()
                results[key] = response.json()
        return results

    async def set_enabled(self, connection: FRMConnection, object_id: str, status: bool) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{connection.normalized_base_url}/setEnabled",
                headers=self._headers(connection.token),
                json={"ID": object_id, "status": status},
            )
            response.raise_for_status()
            return response.json()

    async def set_switch(
        self,
        connection: FRMConnection,
        object_id: str,
        *,
        status: bool | None = None,
        name: str | None = None,
        priority: int | None = None,
    ) -> Any:
        payload: dict[str, Any] = {"ID": object_id}
        if status is not None:
            payload["status"] = status
        if name is not None:
            payload["name"] = name
        if priority is not None:
            payload["priority"] = priority
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{connection.normalized_base_url}/setSwitches",
                headers=self._headers(connection.token),
                json=payload,
            )
            response.raise_for_status()
            return response.json()
