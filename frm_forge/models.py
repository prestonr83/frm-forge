from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class ConnectionConfig(Base):
    __tablename__ = "connection_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    frm_base_url: Mapped[str] = mapped_column(String(512), default="")
    frm_token: Mapped[str] = mapped_column(String(512), default="")
    default_schedule_timezone: Mapped[str] = mapped_column(String(80), default="local")
    refresh_seconds: Mapped[int] = mapped_column(Integer, default=10)
    use_websocket: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_import_url: Mapped[str] = mapped_column(String(512), default="")
    import_refresh_minutes: Mapped[int] = mapped_column(Integer, default=5)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Dashboard(Base):
    __tablename__ = "dashboard"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    widgets: Mapped[list["DashboardWidget"]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="DashboardWidget.position",
    )


class DashboardWidget(Base):
    __tablename__ = "dashboard_widget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(ForeignKey("dashboard.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120))
    widget_kind: Mapped[str] = mapped_column(String(80))
    size: Mapped[str] = mapped_column(String(24), default="normal")
    position: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    dashboard: Mapped[Dashboard] = relationship(back_populates="widgets")


class NameMapping(Base):
    __tablename__ = "name_mapping"
    __table_args__ = (UniqueConstraint("object_id", "category", name="uq_name_mapping_object_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_id: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(80), default="general")
    display_name: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AutomationRule(Base):
    __tablename__ = "automation_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    rule_type: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_object_id: Mapped[str] = mapped_column(String(255))
    action_status: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_days: Mapped[list[int] | None] = mapped_column(JSON, default=list, nullable=True)
    schedule_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    schedule_timezone: Mapped[str] = mapped_column(String(64), default="local")
    metric: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(12), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_text: Mapped[str] = mapped_column(String(255), default="")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=5)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_schedule_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    events: Mapped[list["AutomationEvent"]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class AutomationEvent(Base):
    __tablename__ = "automation_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("automation_rule.id", ondelete="SET NULL"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    level: Mapped[str] = mapped_column(String(16), default="info")
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    rule: Mapped[AutomationRule | None] = relationship(back_populates="events")
