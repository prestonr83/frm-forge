from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .config import get_settings
from .db import SessionLocal
from .frm_client import FRMClient, FRMConnection
from .models import AutomationEvent, AutomationRule
from .repository import list_rules, load_connection_config, sync_imported_rules
from .snapshot_service import SnapshotService


def compare(left: float, operator: str, right: float) -> bool:
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    return False


def schedule_key(now: datetime) -> str:
    return f"{now.year}-{now.month}-{now.day}-{now.hour}-{now.minute}"


def cooldown_open(rule: AutomationRule, now: datetime) -> bool:
    if rule.last_triggered_at is None:
        return True
    minutes_since = (now - rule.last_triggered_at).total_seconds() / 60
    return minutes_since >= rule.cooldown_minutes


def schedule_matches(rule: AutomationRule, now: datetime) -> bool:
    if not rule.schedule_days or not rule.schedule_time:
        return False
    try:
        hours, minutes = [int(part) for part in rule.schedule_time.split(":", 1)]
    except ValueError:
        return False
    return now.weekday() + 1 in rule.schedule_days and now.hour == hours and now.minute == minutes


def resolve_schedule_now(rule: AutomationRule, default_timezone: str) -> datetime:
    requested = (rule.schedule_timezone or "").strip() or (default_timezone or "local").strip()
    if requested.lower() == "local":
        env_tz = (os.getenv("TZ") or "").strip()
        requested = env_tz if env_tz and env_tz.lower() != "local" else ""
    if requested:
        try:
            return datetime.now(UTC).astimezone(ZoneInfo(requested))
        except ZoneInfoNotFoundError:
            pass
    return datetime.now().astimezone()


def metric_value(rule: AutomationRule, snapshot: dict[str, Any]) -> float | None:
    if rule.metric == "power.margin.min":
        values = [
            float(circuit.get("PowerProduction", 0) or 0) - float(circuit.get("PowerConsumed", 0) or 0)
            for circuit in snapshot.get("power", [])
        ]
        return min(values) if values else None
    if rule.metric == "power.battery.min":
        values = [float(circuit.get("BatteryPercent", 0) or 0) for circuit in snapshot.get("power", [])]
        return min(values) if values else None
    if rule.metric == "power.fuse.count":
        return float(sum(1 for circuit in snapshot.get("power", []) if circuit.get("FuseTriggered")))
    if rule.metric == "factory.paused.count":
        return float(sum(1 for machine in snapshot.get("factory", []) if machine.get("IsPaused")))
    if rule.metric == "factory.utilization.avg":
        values = [
            float((machine.get("production") or [{}])[0].get("ProdPercent", 0) or 0)
            for machine in snapshot.get("factory", [])
            if machine.get("production")
        ]
        return sum(values) / len(values) if values else None
    if rule.metric in {"prod.item.current", "prod.item.max"}:
        match_text = (rule.match_text or "").lower()
        for entry in snapshot.get("prod_stats", []):
            if match_text and match_text not in str(entry.get("Name", "")).lower() and match_text not in str(entry.get("ClassName", "")).lower():
                continue
            key = "CurrentProd" if rule.metric == "prod.item.current" else "MaxProd"
            return float(entry.get(key, 0) or 0)
        return None
    return None


class AutomationService:
    def __init__(self, snapshot_service: SnapshotService, client: FRMClient) -> None:
        self.snapshot_service = snapshot_service
        self.client = client
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_import_sync: datetime | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def run_rule_now(self, rule_id: int) -> None:
        with SessionLocal() as session:
            rule = session.get(AutomationRule, rule_id)
            if rule is None:
                raise ValueError("Rule not found.")
            await self._execute_rule(session, rule, detail_prefix="Manual run")
            session.commit()

    async def sync_imported_rules_now(self) -> None:
        self._last_import_sync = None
        await self._sync_imported_rules_if_needed()

    async def _loop(self) -> None:
        settings = get_settings()
        while not self._stop.is_set():
            try:
                await self._sync_imported_rules_if_needed()
                await self._evaluate_rules()
            except Exception as error:
                with SessionLocal() as session:
                    session.add(
                        AutomationEvent(
                            level="error",
                            title="Automation engine error",
                            detail=str(error),
                        )
                    )
                    session.commit()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.automation_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _sync_imported_rules_if_needed(self) -> None:
        with SessionLocal() as session:
            config = load_connection_config(session)
            url = config.schedule_import_url.strip()
            every_minutes = max(config.import_refresh_minutes, 1)
        if not url:
            return
        now = datetime.utcnow()
        if self._last_import_sync and (now - self._last_import_sync).total_seconds() < every_minutes * 60:
            return

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Imported rule feed must return a JSON array.")

        normalized = [self._normalize_imported_rule(item) for item in payload]
        with SessionLocal() as session:
            sync_imported_rules(session, normalized)
            session.add(
                AutomationEvent(
                    level="info",
                    title="Imported rules synced",
                    detail=f"Loaded {len(normalized)} imported rules.",
                )
            )
            session.commit()
        self._last_import_sync = now

    def _normalize_imported_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        rule_type = payload.get("rule_type") or payload.get("type")
        target_type = payload.get("target_type") or payload.get("targetType")
        target_object_id = payload.get("target_object_id") or payload.get("targetId")
        action_status = payload.get("action_status")
        if action_status is None:
            action_status = (payload.get("action") or {}).get("status")
        return {
            "name": payload["name"],
            "rule_type": rule_type,
            "enabled": payload.get("enabled", True),
            "target_type": target_type,
            "target_object_id": target_object_id,
            "action_status": bool(action_status),
            "schedule_days": payload.get("schedule_days") or (payload.get("schedule") or {}).get("days") or [],
            "schedule_time": payload.get("schedule_time") or (payload.get("schedule") or {}).get("time"),
            "schedule_timezone": payload.get("schedule_timezone") or (payload.get("schedule") or {}).get("timezone") or "local",
            "metric": payload.get("metric"),
            "operator": payload.get("operator"),
            "threshold": payload.get("threshold"),
            "match_text": payload.get("match_text") or payload.get("matchText") or "",
            "cooldown_minutes": payload.get("cooldown_minutes") or payload.get("cooldownMinutes") or 5,
        }

    async def _evaluate_rules(self) -> None:
        state = self.snapshot_service.get_state()
        if state.status != "online":
            return
        now = datetime.utcnow()
        with SessionLocal() as session:
            config = load_connection_config(session)
            if not config.frm_base_url.strip():
                return
            connection = FRMConnection(config.frm_base_url, config.frm_token)
            rules = list_rules(session)
            for rule in rules:
                if not rule.enabled:
                    continue
                if rule.rule_type == "schedule":
                    schedule_now = resolve_schedule_now(rule, config.default_schedule_timezone)
                    key = schedule_key(schedule_now)
                    if not schedule_matches(rule, schedule_now) or not cooldown_open(rule, now) or rule.last_schedule_key == key:
                        continue
                    await self._execute_rule(session, rule, connection=connection, schedule_key_value=key)
                    continue
                value = metric_value(rule, state.data)
                rule.last_value = value
                if value is None or rule.threshold is None or not cooldown_open(rule, now):
                    continue
                if compare(value, rule.operator or "", rule.threshold):
                    await self._execute_rule(session, rule, connection=connection, metric_value_result=value)
            session.commit()

    async def _execute_rule(
        self,
        session,
        rule: AutomationRule,
        *,
        connection: FRMConnection | None = None,
        schedule_key_value: str | None = None,
        metric_value_result: float | None = None,
        detail_prefix: str = "Rule executed",
    ) -> None:
        config = load_connection_config(session)
        connection = connection or FRMConnection(config.frm_base_url, config.frm_token)
        if not connection.token.strip():
            raise RuntimeError("FRM token is required for write actions.")
        if rule.target_type == "switch":
            await self.client.set_switch(connection, rule.target_object_id, status=rule.action_status)
        else:
            await self.client.set_enabled(connection, rule.target_object_id, rule.action_status)

        rule.last_triggered_at = datetime.utcnow()
        if schedule_key_value:
            rule.last_schedule_key = schedule_key_value

        detail = f"{detail_prefix}: {rule.target_type} {rule.target_object_id} -> {rule.action_status}"
        if metric_value_result is not None:
            detail += f" at value {metric_value_result}"

        session.add(
            AutomationEvent(
                rule_id=rule.id,
                level="ok",
                title=rule.name,
                detail=detail,
                payload_json={"target": rule.target_object_id, "status": rule.action_status},
            )
        )
