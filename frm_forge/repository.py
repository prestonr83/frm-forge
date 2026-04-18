from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .config import get_settings
from .db import Base, engine
from .models import AutomationEvent, AutomationRule, ConnectionConfig, Dashboard, DashboardWidget, NameMapping

DEFAULT_WIDGETS = [
    ("session-pulse", "Session Pulse", "session_pulse", "normal", {}),
    ("power-trend", "Power Trend", "power_trend", "wide", {}),
    ("production-flow", "Production Flow", "production_flow", "wide", {}),
    ("switchboard", "Switchboard", "switchboard", "wide", {}),
    ("factory-pulse", "Factory Pulse", "factory_pulse", "normal", {}),
    ("automation-feed", "Automation Feed", "automation_feed", "wide", {}),
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "dashboard"


def unique_dashboard_slug(session: Session, name: str) -> str:
    base = slugify(name)
    candidate = base
    counter = 2
    while session.scalar(select(Dashboard.id).where(Dashboard.slug == candidate).limit(1)) is not None:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def init_database() -> None:
    Base.metadata.create_all(engine)
    settings = get_settings()
    with Session(engine, expire_on_commit=False) as session:
        config = session.get(ConnectionConfig, 1)
        if config is None:
            config = ConnectionConfig(
                id=1,
                frm_base_url=settings.bootstrap_frm_base_url,
                frm_token=settings.bootstrap_frm_token,
                default_schedule_timezone=settings.bootstrap_default_schedule_timezone,
                refresh_seconds=settings.bootstrap_refresh_seconds,
                use_websocket=settings.bootstrap_use_websocket,
            )
            session.add(config)

        if session.scalar(select(Dashboard).limit(1)) is None:
            create_dashboard(
                session,
                name="Ops Deck",
                description="Core live operational wallboard.",
                widget_specs=DEFAULT_WIDGETS,
            )
            create_dashboard(
                session,
                name="Power Floor",
                description="Grid, switches, and automation posture.",
                widget_specs=[
                    ("power-floor-trend", "Power Trend", "power_trend", "wide", {}),
                    ("power-floor-switches", "Switchboard", "switchboard", "wide", {}),
                    ("power-floor-factory", "Factory Pulse", "factory_pulse", "normal", {}),
                    ("power-floor-automation", "Automation Feed", "automation_feed", "normal", {}),
                ],
            )
        session.commit()


def create_dashboard(
    session: Session,
    name: str,
    description: str = "",
    widget_specs: Iterable[tuple[str, str, str, str, dict]] | None = None,
) -> Dashboard:
    dashboard = Dashboard(slug=unique_dashboard_slug(session, name), name=name, description=description)
    session.add(dashboard)
    session.flush()
    if widget_specs:
        for position, (slug, title, kind, size, config) in enumerate(widget_specs):
            session.add(
                DashboardWidget(
                    dashboard_id=dashboard.id,
                    title=title,
                    widget_kind=kind,
                    size=size,
                    position=position,
                    config_json={"slug": slug, **config},
                )
            )
    return dashboard


def load_connection_config(session: Session) -> ConnectionConfig:
    config = session.get(ConnectionConfig, 1)
    if config is None:
        raise RuntimeError("Connection config was not initialized.")
    return config


def list_dashboards(session: Session) -> list[Dashboard]:
    return list(
        session.scalars(
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .order_by(Dashboard.created_at.asc())
        )
    )


def get_dashboard(session: Session, dashboard_id: int) -> Dashboard | None:
    return session.scalar(
        select(Dashboard)
        .where(Dashboard.id == dashboard_id)
        .options(selectinload(Dashboard.widgets))
    )


def add_widget(
    session: Session,
    dashboard_id: int,
    title: str,
    widget_kind: str,
    size: str = "normal",
    config_json: dict | None = None,
) -> DashboardWidget:
    current_count = session.scalar(
        select(func.count(DashboardWidget.id)).where(DashboardWidget.dashboard_id == dashboard_id)
    )
    widget = DashboardWidget(
        dashboard_id=dashboard_id,
        title=title,
        widget_kind=widget_kind,
        size=size,
        position=current_count or 0,
        config_json=config_json or {},
    )
    session.add(widget)
    return widget


def list_name_mappings(session: Session) -> list[NameMapping]:
    return list(session.scalars(select(NameMapping).order_by(NameMapping.display_name.asc())))


def mapping_lookup(session: Session) -> dict[str, NameMapping]:
    return {mapping.object_id: mapping for mapping in list_name_mappings(session)}


def list_rules(session: Session) -> list[AutomationRule]:
    return list(session.scalars(select(AutomationRule).order_by(AutomationRule.created_at.desc())))


def list_events(session: Session, limit: int = 20) -> list[AutomationEvent]:
    return list(session.scalars(select(AutomationEvent).order_by(AutomationEvent.occurred_at.desc()).limit(limit)))


def sync_imported_rules(session: Session, rules: list[dict]) -> None:
    session.execute(delete(AutomationRule).where(AutomationRule.source == "imported"))
    for payload in rules:
        session.add(
            AutomationRule(
                name=payload["name"],
                rule_type=payload["rule_type"],
                enabled=payload.get("enabled", True),
                target_type=payload["target_type"],
                target_object_id=payload["target_object_id"],
                action_status=payload["action_status"],
                schedule_days=payload.get("schedule_days", []),
                schedule_time=payload.get("schedule_time"),
                schedule_timezone=payload.get("schedule_timezone", "local"),
                metric=payload.get("metric"),
                operator=payload.get("operator"),
                threshold=payload.get("threshold"),
                match_text=payload.get("match_text", ""),
                cooldown_minutes=payload.get("cooldown_minutes", 5),
                source="imported",
            )
        )
