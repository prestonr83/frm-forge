from __future__ import annotations

import asyncio
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from nicegui import app, ui

from .automation import AutomationService
from .config import get_settings
from .db import SessionLocal
from .frm_client import FRMClient, FRMConnection
from .models import AutomationRule, DashboardWidget, NameMapping
from .repository import (
    add_widget,
    create_dashboard,
    get_dashboard,
    init_database,
    list_dashboards,
    list_events,
    list_name_mappings,
    list_rules,
    load_connection_config,
    mapping_lookup,
)
from .snapshot_service import SnapshotService
from .ui.rendering import (
    alerts,
    format_compact,
    format_coords,
    format_percent,
    format_power,
    format_rate,
    format_number,
    map_html,
    ranked_rows,
    spark_chart,
    summary,
    tone,
)
from .ui.theme import APP_CSS

settings = get_settings()
frm_client = FRMClient()
snapshot_service = SnapshotService(frm_client)
automation_service = AutomationService(snapshot_service, frm_client)
services_started = False
STATIC_DIR = Path(__file__).with_name("static")

if STATIC_DIR.exists():
    app.add_static_files("/assets", str(STATIC_DIR))

WIDGET_CATALOG = {
    "session_pulse": "Session Pulse",
    "power_trend": "Power Trend",
    "production_flow": "Throughput Board",
    "switchboard": "Switchboard",
    "factory_pulse": "Factory Pulse",
    "automation_feed": "Automation Feed",
    "machine_detail": "Machine Detail",
    "switch_detail": "Switch Detail",
}
RULE_METRICS = {
    "power.margin.min": "Lowest power margin",
    "power.battery.min": "Lowest battery percent",
    "power.fuse.count": "Triggered fuse count",
    "factory.paused.count": "Paused factory count",
    "factory.utilization.avg": "Average factory utilization",
    "prod.item.current": "Item current production",
    "prod.item.max": "Item max production",
}
DAY_OPTIONS = {
    "Mon": 1,
    "Tue": 2,
    "Wed": 3,
    "Thu": 4,
    "Fri": 5,
    "Sat": 6,
    "Sun": 7,
}


def ensure_started() -> None:
    global services_started
    if services_started:
        return
    init_database()
    snapshot_service.start()
    automation_service.start()
    services_started = True


def friendly_name(object_id: str | None, fallback: str, mappings: dict[str, NameMapping]) -> str:
    if object_id and object_id in mappings:
        return mappings[object_id].display_name
    return fallback


def machine_status(machine: dict) -> tuple[str, str]:
    if machine.get("IsPaused"):
        return "Paused", "warn"
    if not machine.get("IsConfigured", True):
        return "Unconfigured", "error"
    if machine.get("IsProducing"):
        return "Producing", "ok"
    return "Idle", "info"


def schedule_time_valid(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return True


def default_rule_name(name: str, rule_type: str, target_type: str, target_object_id: str) -> str:
    cleaned = name.strip()
    if cleaned:
        return cleaned
    short_target = target_object_id.strip() or "target"
    return f"{rule_type.title()} {target_type} {short_target}"


def day_labels(days: list[int] | None) -> str:
    if not days:
        return "No days"
    labels = [label for label, value in DAY_OPTIONS.items() if value in days]
    return ", ".join(labels) or "No days"


def production_detail(entry: dict[str, Any]) -> str:
    current = float(entry.get("CurrentProd", 0) or 0)
    maximum = float(entry.get("MaxProd", 0) or 0)
    if maximum > 0:
        return f"Max {format_rate(maximum)} | {format_percent((current / maximum) * 100)} of cap"
    return f"Current {format_rate(current)}"


def widget_html(widget: DashboardWidget, snapshot: dict[str, Any], mappings: dict[str, NameMapping], events: list) -> str:
    kind = widget.widget_kind
    title = widget.title
    if kind == "session_pulse":
        session_info = snapshot.get("session_info") or {}
        return (
            f'<div class="frm-card"><div style="font-weight:700">{escape(title)}</div>'
            f'<div class="frm-metric-grid" style="margin-top:12px">'
            f'<div class="frm-metric"><div class="frm-metric-label">Save</div><span class="frm-metric-value">{escape(session_info.get("SessionName", "No session"))}</span></div>'
            f'<div class="frm-metric"><div class="frm-metric-label">Clock</div><span class="frm-metric-value">{session_info.get("Hours", "--")}:{str(session_info.get("Minutes", "--")).zfill(2)}</span></div>'
            f'<div class="frm-metric"><div class="frm-metric-label">Duration</div><span class="frm-metric-value">{escape(session_info.get("TotalPlayDurationText", "--"))}</span></div>'
            f'</div></div>'
        )
    if kind == "power_trend":
        history = snapshot_service.get_state().history["power"]
        return spark_chart(
            title,
            "Live output, consumption, and installed capacity.",
            [
                {"label": "Output", "values": [point["production"] for point in history], "color": "#89dceb", "fill": "#89dceb18"},
                {"label": "Consumption", "values": [point["consumption"] for point in history], "color": "#fab387", "fill": "#fab38716"},
                {"label": "Capacity", "values": [point["capacity"] for point in history], "color": "#b4befe", "fill": "#b4befe12"},
            ],
            formatter=format_power,
        )
    if kind == "production_flow":
        items = sorted(snapshot.get("prod_stats", []), key=lambda entry: float(entry.get("CurrentProd", 0) or 0), reverse=True)
        return ranked_rows(
            title,
            "Highest current output items.",
            [
                {
                    "label": entry.get("Name", "Item"),
                    "value": float(entry.get("CurrentProd", 0) or 0),
                    "detail": production_detail(entry),
                }
                for entry in items[:7]
            ],
            formatter=format_rate,
        )
    if kind == "switchboard":
        rows = []
        for entry in snapshot.get("switches", [])[:5]:
            rows.append(
                f'<div class="frm-row"><div style="display:flex;justify-content:space-between;gap:12px">'
                f'<strong>{escape(friendly_name(entry.get("ID"), entry.get("Name") or entry.get("SwitchTag") or entry.get("ID", "Switch"), mappings))}</strong>'
                f'<span class="frm-status {tone("ok" if entry.get("IsOn") else "warn")}">{("On" if entry.get("IsOn") else "Off")}</span>'
                f'</div><div class="frm-caption" style="margin-top:8px">Priority {entry.get("Priority", -1)}</div></div>'
            )
        body = "".join(rows) or '<div class="frm-caption">No switches.</div>'
        return f'<div class="frm-card"><div style="font-weight:700">{escape(title)}</div><div style="display:grid;gap:12px;margin-top:12px">{body}</div></div>'
    if kind == "factory_pulse":
        rows = []
        for machine in snapshot.get("factory", [])[:5]:
            label, level = machine_status(machine)
            rows.append(
                f'<div class="frm-row"><div style="display:flex;justify-content:space-between;gap:12px">'
                f'<strong>{escape(friendly_name(machine.get("ID"), machine.get("Name", "Machine"), mappings))}</strong>'
                f'<span class="frm-status {tone(level)}">{escape(label)}</span></div>'
                f'<div class="frm-caption" style="margin-top:8px">{escape(machine.get("Recipe") or machine.get("ClassName") or "")}</div></div>'
            )
        body = "".join(rows) or '<div class="frm-caption">No machines.</div>'
        return f'<div class="frm-card"><div style="font-weight:700">{escape(title)}</div><div style="display:grid;gap:12px;margin-top:12px">{body}</div></div>'
    if kind == "automation_feed":
        rows = []
        for event in events[:5]:
            rows.append(
                f'<div class="frm-row"><div style="display:flex;justify-content:space-between;gap:12px">'
                f'<strong>{escape(event.title)}</strong><span class="frm-status {tone(event.level)}">{escape(event.level)}</span></div>'
                f'<div class="frm-caption" style="margin-top:8px">{escape(event.detail)}</div></div>'
            )
        body = "".join(rows) or '<div class="frm-caption">No automation runs yet.</div>'
        return f'<div class="frm-card"><div style="font-weight:700">{escape(title)}</div><div style="display:grid;gap:12px;margin-top:12px">{body}</div></div>'
    if kind == "machine_detail":
        target_id = widget.config_json.get("object_id")
        machine = next((entry for entry in snapshot.get("factory", []) if entry.get("ID") == target_id), None)
        if not machine:
            return f'<div class="frm-card"><div class="frm-caption">{escape(title)} is unavailable.</div></div>'
        return (
            f'<div class="frm-card"><div style="font-weight:700">{escape(title)}</div><div class="frm-metric-grid" style="margin-top:12px">'
            f'<div class="frm-metric"><div class="frm-metric-label">Name</div><span class="frm-metric-value">{escape(friendly_name(machine.get("ID"), machine.get("Name", "Machine"), mappings))}</span></div>'
            f'<div class="frm-metric"><div class="frm-metric-label">Recipe</div><span class="frm-metric-value">{escape(machine.get("Recipe") or "None")}</span></div>'
            f'<div class="frm-metric"><div class="frm-metric-label">Output</div><span class="frm-metric-value">{format_rate((machine.get("production") or [{}])[0].get("CurrentProd", 0))}</span></div>'
            f'</div><div class="frm-caption" style="margin-top:10px">{escape(format_coords(machine.get("location")))}</div></div>'
        )
    if kind == "switch_detail":
        target_id = widget.config_json.get("object_id")
        power_switch = next((entry for entry in snapshot.get("switches", []) if entry.get("ID") == target_id), None)
        if not power_switch:
            return f'<div class="frm-card"><div class="frm-caption">{escape(title)} is unavailable.</div></div>'
        return (
            f'<div class="frm-card"><div style="font-weight:700">{escape(title)}</div><div class="frm-metric-grid" style="margin-top:12px">'
            f'<div class="frm-metric"><div class="frm-metric-label">Name</div><span class="frm-metric-value">{escape(friendly_name(power_switch.get("ID"), power_switch.get("Name") or power_switch.get("ID", "Switch"), mappings))}</span></div>'
            f'<div class="frm-metric"><div class="frm-metric-label">State</div><span class="frm-metric-value">{("On" if power_switch.get("IsOn") else "Off")}</span></div>'
            f'<div class="frm-metric"><div class="frm-metric-label">Priority</div><span class="frm-metric-value">{power_switch.get("Priority", -1)}</span></div>'
            f'</div><div class="frm-caption" style="margin-top:10px">{escape(format_coords(power_switch.get("location")))}</div></div>'
        )
    return f'<div class="frm-card"><div class="frm-caption">Widget {escape(kind)} is not implemented.</div></div>'


@ui.page("/")
async def main_page() -> None:
    ensure_started()
    ui.add_head_html(APP_CSS)

    with SessionLocal() as session:
        dashboards = list_dashboards(session)
        config = load_connection_config(session)
        page_state = {
            "dashboard_id": dashboards[0].id if dashboards else None,
            "factory_search": "",
            "factory_mode": "all",
            "factory_class_search": "",
            "map_layers": {"players": True, "switches": True, "markers": True, "factory": False},
        }

    async def refresh_snapshot_action() -> None:
        try:
            await snapshot_service.refresh_now()
            refresh_dynamic_sections()
            ui.notify("FRM snapshot refreshed.", type="positive")
        except Exception as error:
            ui.notify(str(error), type="negative")

    def refresh_dynamic_sections() -> None:
        render_hero.refresh()
        render_overview.refresh()
        render_factory_list.refresh()
        render_power_summary.refresh()
        render_switch_editor.refresh()
        render_map_view.refresh()
        render_rules_and_history.refresh()
        render_dashboard_view.refresh()

    def current_mappings() -> dict[str, NameMapping]:
        with SessionLocal() as session:
            return mapping_lookup(session)

    def current_snapshot() -> dict[str, Any]:
        return snapshot_service.get_state().data

    async def save_connection(
        base_url: str,
        token: str,
        refresh_seconds: int,
        import_url: str,
        import_refresh: int,
        default_schedule_timezone: str,
    ) -> None:
        timezone_value = default_schedule_timezone.strip() or "local"
        with SessionLocal() as session:
            saved_config = load_connection_config(session)
            saved_config.frm_base_url = base_url.strip()
            saved_config.frm_token = token.strip()
            saved_config.default_schedule_timezone = timezone_value
            saved_config.refresh_seconds = max(int(refresh_seconds or 10), 5)
            saved_config.schedule_import_url = import_url.strip()
            saved_config.import_refresh_minutes = max(int(import_refresh or 5), 1)
            session.commit()
        config.frm_base_url = base_url.strip()
        config.frm_token = token.strip()
        config.default_schedule_timezone = timezone_value
        config.refresh_seconds = max(int(refresh_seconds or 10), 5)
        config.schedule_import_url = import_url.strip()
        config.import_refresh_minutes = max(int(import_refresh or 5), 1)
        message = "Connection settings saved."
        message_type = "positive"
        try:
            await snapshot_service.refresh_now()
        except Exception as error:
            message = f"Connection saved, but FRM refresh failed: {error}"
            message_type = "warning"
        refresh_dynamic_sections()
        ui.notify(message, type=message_type)

    def save_name_mapping(object_id: str, category: str, display_name: str, notes: str) -> None:
        if not object_id.strip() or not display_name.strip():
            ui.notify("Object ID and display name are required.", type="warning")
            return
        with SessionLocal() as session:
            existing = next(
                (mapping for mapping in list_name_mappings(session) if mapping.object_id == object_id.strip() and mapping.category == category.strip()),
                None,
            )
            if existing:
                existing.display_name = display_name.strip()
                existing.notes = notes.strip()
            else:
                session.add(
                    NameMapping(
                        object_id=object_id.strip(),
                        category=category.strip() or "general",
                        display_name=display_name.strip(),
                        notes=notes.strip(),
                    )
                )
            session.commit()
        refresh_dynamic_sections()
        render_settings_lists.refresh()
        ui.notify("Name mapping saved.", type="positive")

    def delete_mapping(mapping_id: int) -> None:
        with SessionLocal() as session:
            mapping = session.get(NameMapping, mapping_id)
            if mapping is not None:
                session.delete(mapping)
                session.commit()
        refresh_dynamic_sections()
        render_settings_lists.refresh()

    def create_rule(payload: dict[str, Any]) -> None:
        try:
            with SessionLocal() as session:
                session.add(AutomationRule(**payload))
                session.commit()
        except Exception as error:
            ui.notify(str(error), type="negative")
            return
        render_rules_and_history.refresh()
        ui.notify("Rule saved.", type="positive")

    def toggle_rule_enabled(rule_id: int) -> None:
        with SessionLocal() as session:
            rule = session.get(AutomationRule, rule_id)
            if rule is not None:
                rule.enabled = not rule.enabled
                session.commit()
        render_rules_and_history.refresh()

    def delete_rule(rule_id: int) -> None:
        with SessionLocal() as session:
            rule = session.get(AutomationRule, rule_id)
            if rule is not None:
                session.delete(rule)
                session.commit()
        render_rules_and_history.refresh()

    async def run_rule(rule_id: int) -> None:
        try:
            await automation_service.run_rule_now(rule_id)
            await snapshot_service.refresh_now()
            refresh_dynamic_sections()
            render_switch_editor.refresh()
            ui.notify("Rule executed.", type="positive")
        except Exception as error:
            ui.notify(str(error), type="negative")

    async def sync_imported_rules_action() -> None:
        try:
            await automation_service.sync_imported_rules_now()
            refresh_dynamic_sections()
            ui.notify("Imported rules synced.", type="positive")
        except Exception as error:
            ui.notify(str(error), type="negative")

    def create_dashboard_action(name: str, description: str) -> None:
        if not name.strip():
            ui.notify("Dashboard name is required.", type="warning")
            return
        with SessionLocal() as session:
            dashboard = create_dashboard(session, name=name.strip(), description=description.strip())
            session.commit()
            page_state["dashboard_id"] = dashboard.id
        render_dashboard_view.refresh()
        ui.notify("Dashboard created.", type="positive")

    def delete_dashboard_action(dashboard_id: int) -> None:
        with SessionLocal() as session:
            dashboard = get_dashboard(session, dashboard_id)
            if dashboard is not None:
                session.delete(dashboard)
                session.commit()
            dashboards = list_dashboards(session)
            page_state["dashboard_id"] = dashboards[0].id if dashboards else None
        render_dashboard_view.refresh()

    def update_widget_layout(widget_id: int, direction: int) -> None:
        with SessionLocal() as session:
            widget = session.get(DashboardWidget, widget_id)
            if widget is None:
                return
            siblings = list(get_dashboard(session, widget.dashboard_id).widgets)
            index = next((i for i, entry in enumerate(siblings) if entry.id == widget_id), None)
            if index is None:
                return
            swap_index = index + direction
            if swap_index < 0 or swap_index >= len(siblings):
                return
            siblings[index].position, siblings[swap_index].position = siblings[swap_index].position, siblings[index].position
            session.commit()
        render_dashboard_view.refresh()

    def delete_widget_action(widget_id: int) -> None:
        with SessionLocal() as session:
            widget = session.get(DashboardWidget, widget_id)
            if widget is not None:
                session.delete(widget)
                session.commit()
        render_dashboard_view.refresh()

    async def add_widget_to_dashboard(title: str, kind: str, config_json: dict | None = None) -> None:
        if page_state["dashboard_id"] is None:
            ui.notify("Create a dashboard first.", type="warning")
            return
        with SessionLocal() as session:
            add_widget(
                session,
                dashboard_id=page_state["dashboard_id"],
                title=title,
                widget_kind=kind,
                config_json=config_json or {},
            )
            session.commit()
        render_dashboard_view.refresh()
        ui.notify(f"Pinned {title} to the active dashboard.", type="positive")

    async def toggle_machine(machine_id: str, status: bool) -> None:
        with SessionLocal() as session:
            config = load_connection_config(session)
            if not config.frm_token.strip():
                ui.notify("Set the FRM token before using write actions.", type="warning")
                return
            await frm_client.set_enabled(FRMConnection(config.frm_base_url, config.frm_token), machine_id, status)
        await snapshot_service.refresh_now()
        refresh_dynamic_sections()
        ui.notify("Factory machine updated.", type="positive")

    async def toggle_switch(switch_id: str, status: bool) -> None:
        with SessionLocal() as session:
            config = load_connection_config(session)
            if not config.frm_token.strip():
                ui.notify("Set the FRM token before using write actions.", type="warning")
                return
            await frm_client.set_switch(FRMConnection(config.frm_base_url, config.frm_token), switch_id, status=status)
        await snapshot_service.refresh_now()
        refresh_dynamic_sections()
        render_switch_editor.refresh()
        ui.notify("Switch updated.", type="positive")

    async def save_switch_details(switch_id: str, name: str, priority: int) -> None:
        with SessionLocal() as session:
            config = load_connection_config(session)
            if not config.frm_token.strip():
                ui.notify("Set the FRM token before using write actions.", type="warning")
                return
            await frm_client.set_switch(
                FRMConnection(config.frm_base_url, config.frm_token),
                switch_id,
                name=name,
                priority=priority,
            )
        await snapshot_service.refresh_now()
        refresh_dynamic_sections()
        render_switch_editor.refresh()
        ui.notify("Switch details saved.", type="positive")

    with ui.column().classes("frm-shell w-full gap-6"):
        @ui.refreshable
        def render_hero() -> None:
            state = snapshot_service.get_state()
            data = state.data
            info = summary(data)
            session_info = data.get("session_info") or {}
            power_margin = info["power_margin"]
            connection_tone = tone("ok" if state.status == "online" else "warn" if state.status == "idle" else "error")
            balance_tone = tone("error" if power_margin < 0 else "warn" if power_margin < 400 else "ok")
            balance_copy = (
                f"Consumption is ahead by {format_power(abs(power_margin))}."
                if power_margin < 0
                else f"{format_power(info['power_production'])} output / {format_power(info['power_consumption'])} consumption"
            )
            ui.html(
                f'<section class="frm-hero">'
                f'<span class="frm-eyebrow">SCC // FRM</span>'
                f'<div class="frm-title">Statisfactory Control Center</div>'
                f'<div class="frm-muted" style="max-width:840px">Live output, consumption, switches, automations, and field positions in one clean control room.</div>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px"><span class="frm-status {connection_tone}">{escape(state.status)} {escape(state.last_error or "")}</span>'
                f'<span class="frm-chip">Last sync {escape(state.last_refresh_at.isoformat(timespec="seconds") if state.last_refresh_at else "never")}</span>'
                f'<span class="frm-status {balance_tone}">{("Deficit" if power_margin < 0 else "Surplus")} {escape(format_power(abs(power_margin)))}</span></div>'
                f'<div class="frm-stat-grid" style="margin-top:24px">'
                f'<div class="frm-stat"><div class="frm-stat-label">Session</div><div class="frm-stat-value">{escape(session_info.get("SessionName", "No session"))}</div><div class="frm-muted">{("Day" if session_info.get("IsDay") else "Night") if session_info else "Offline"}</div></div>'
                f'<div class="frm-stat"><div class="frm-stat-label">Power Balance</div><div class="frm-stat-value">{format_power(power_margin)}</div><div class="frm-muted">{escape(balance_copy)}</div></div>'
                f'<div class="frm-stat"><div class="frm-stat-label">Factory Utilization</div><div class="frm-stat-value">{format_percent(info["avg_utilization"])}</div><div class="frm-muted">{info["producing_factories"]} producing, {info["paused_factories"]} paused</div></div>'
                f'<div class="frm-stat"><div class="frm-stat-label">Operators</div><div class="frm-stat-value">{info["active_players"]}/{len(data.get("players", []))}</div><div class="frm-muted">{len(data.get("switches", []))} switches tracked</div></div>'
                f'</div></section>'
            ).classes("w-full")

        render_hero()

        with ui.row().classes("w-full justify-between items-center"):
            with ui.tabs().classes("text-white") as tabs:
                overview_tab = ui.tab("Overview")
                factory_tab = ui.tab("Factory")
                power_tab = ui.tab("Power")
                map_tab = ui.tab("Map")
                automation_tab = ui.tab("Automations")
                dashboard_tab = ui.tab("Dashboards")
                settings_tab = ui.tab("Settings")
            ui.button("Refresh FRM", on_click=refresh_snapshot_action)

        with ui.tab_panels(tabs, value=overview_tab).classes("w-full"):
            with ui.tab_panel(overview_tab):
                @ui.refreshable
                def render_overview() -> None:
                    state = snapshot_service.get_state()
                    data = state.data
                    info = summary(data)
                    production_items = sorted(data.get("prod_stats", []), key=lambda item: float(item.get("CurrentProd", 0) or 0), reverse=True)
                    with ui.column().classes("w-full gap-4"):
                        with ui.row().classes("w-full gap-4 items-start"):
                            ui.html(
                                spark_chart(
                                    "Power Balance",
                                    "Live output, consumption, and installed capacity from FRM.",
                                    [
                                        {"label": "Output", "values": [point["production"] for point in state.history["power"]], "color": "#89dceb", "fill": "#89dceb18"},
                                        {"label": "Consumption", "values": [point["consumption"] for point in state.history["power"]], "color": "#fab387", "fill": "#fab38716"},
                                        {"label": "Capacity", "values": [point["capacity"] for point in state.history["power"]], "color": "#b4befe", "fill": "#b4befe12"},
                                    ],
                                    formatter=format_power,
                                )
                            ).classes("w-full lg:w-8/12")
                            ui.html(
                                "".join(
                                    f'<div class="frm-row" style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;gap:12px"><strong>{escape(item["title"])}</strong><span class="frm-status {tone(item["level"])}">{escape(item["level"])}</span></div><div class="frm-caption" style="margin-top:8px">{escape(item["detail"])}</div></div>'
                                    for item in alerts(data)
                                )
                            ).classes("w-full lg:w-4/12 frm-panel p-4")
                        with ui.row().classes("w-full gap-4 items-start"):
                            ui.html(
                                ranked_rows(
                                    "Top Item Throughput",
                                    "Current item output per minute, with current versus cap called out clearly.",
                                    [
                                        {
                                            "label": item.get("Name", "Item"),
                                            "value": float(item.get("CurrentProd", 0) or 0),
                                            "detail": production_detail(item),
                                        }
                                        for item in production_items[:8]
                                    ],
                                    formatter=format_rate,
                                )
                            ).classes("w-full lg:w-7/12")
                            ui.html(
                                '<div class="frm-card"><div style="font-weight:700">Live Snapshot</div>'
                                f'<div class="frm-metric-grid" style="margin-top:12px">'
                                f'<div class="frm-metric"><div class="frm-metric-label">Players</div><span class="frm-metric-value">{info["active_players"]}</span></div>'
                                f'<div class="frm-metric"><div class="frm-metric-label">Switches Off</div><span class="frm-metric-value">{info["switches_off"]}</span></div>'
                                f'<div class="frm-metric"><div class="frm-metric-label">Fuse Trips</div><span class="frm-metric-value">{info["triggered_fuses"]}</span></div>'
                                f'<div class="frm-metric"><div class="frm-metric-label">Paused</div><span class="frm-metric-value">{info["paused_factories"]}</span></div>'
                                f'</div></div>'
                            ).classes("w-full lg:w-5/12")

                render_overview()

            with ui.tab_panel(factory_tab):
                with ui.row().classes("w-full gap-4 items-end"):
                    search_input = ui.input("Search", placeholder="assembler, aluminum, Build_...").classes("w-full")
                    mode_select = ui.select(
                        {
                            "all": "All machines",
                            "producing": "Producing",
                            "paused": "Paused",
                            "unconfigured": "Unconfigured",
                        },
                        label="Mode",
                        value="all",
                    )
                    class_search = ui.input("Class contains", placeholder="Build_Smelter").classes("w-full")

                search_input.on_value_change(lambda event: (page_state.__setitem__("factory_search", event.value or ""), render_factory_list.refresh()))
                mode_select.on_value_change(lambda event: (page_state.__setitem__("factory_mode", event.value or "all"), render_factory_list.refresh()))
                class_search.on_value_change(lambda event: (page_state.__setitem__("factory_class_search", (event.value or "").lower()), render_factory_list.refresh()))

                @ui.refreshable
                def render_factory_list() -> None:
                    snapshot = current_snapshot()
                    mappings = current_mappings()
                    machines = []
                    search = page_state["factory_search"].lower()
                    class_filter = page_state["factory_class_search"]
                    for machine in snapshot.get("factory", []):
                        status_label, status_level = machine_status(machine)
                        if page_state["factory_mode"] == "producing" and not machine.get("IsProducing"):
                            continue
                        if page_state["factory_mode"] == "paused" and not machine.get("IsPaused"):
                            continue
                        if page_state["factory_mode"] == "unconfigured" and machine.get("IsConfigured", True):
                            continue
                        if class_filter and class_filter not in str(machine.get("ClassName", "")).lower():
                            continue
                        haystack = " ".join(str(machine.get(key, "")) for key in ["Name", "ClassName", "Recipe", "ID"]).lower()
                        if search and search not in haystack:
                            continue
                        machines.append((machine, status_label, status_level))

                    with ui.column().classes("w-full gap-3"):
                        ui.label(f"{len(machines)} machines match the current filters.").classes("frm-muted")
                        if not machines:
                            ui.label("No factory actors match the current filters.").classes("frm-muted")
                        for machine, status_label, status_level in machines[:36]:
                            with ui.card().classes("frm-panel w-full"):
                                with ui.row().classes("w-full justify-between items-start"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(friendly_name(machine.get("ID"), machine.get("Name", "Machine"), mappings)).classes("text-lg font-bold")
                                        ui.label(machine.get("Recipe") or machine.get("ClassName") or "").classes("frm-muted")
                                        ui.label(machine.get("ID") or "").classes("frm-muted text-xs")
                                    ui.html(f'<span class="frm-status {tone(status_level)}">{escape(status_label)}</span>')
                                with ui.row().classes("w-full gap-4"):
                                    ui.html(f'<div class="frm-card w-full"><div class="frm-metric-label">Output</div><div class="frm-metric-value">{format_rate((machine.get("production") or [{}])[0].get("CurrentProd", 0))}</div></div>')
                                    ui.html(f'<div class="frm-card w-full"><div class="frm-metric-label">Speed</div><div class="frm-metric-value">{format_percent(machine.get("ManuSpeed", 0))}</div></div>')
                                    ui.html(f'<div class="frm-card w-full"><div class="frm-metric-label">Power</div><div class="frm-metric-value">{format_power((machine.get("PowerInfo") or {}).get("PowerConsumed", 0))}</div></div>')
                                with ui.row().classes("w-full justify-between items-center gap-4"):
                                    ui.label(format_coords(machine.get("location"))).classes("frm-muted text-sm")
                                    with ui.row().classes("gap-2"):
                                        ui.button(
                                            "Enable" if machine.get("IsPaused") else "Pause",
                                            on_click=lambda machine_id=machine.get("ID"), next_status=bool(machine.get("IsPaused")): asyncio.create_task(toggle_machine(machine_id, next_status)),
                                        )
                                        ui.button(
                                            "Pin Detail",
                                            on_click=lambda machine_id=machine.get("ID"), name=friendly_name(machine.get("ID"), machine.get("Name", "Machine"), mappings): asyncio.create_task(add_widget_to_dashboard(name, "machine_detail", {"object_id": machine_id})),
                                        )

                render_factory_list()

            with ui.tab_panel(power_tab):
                @ui.refreshable
                def render_power_summary() -> None:
                    state = snapshot_service.get_state()
                    data = state.data
                    consumers = sorted(
                        data.get("power_usage", []),
                        key=lambda entry: float((entry.get("PowerInfo") or {}).get("PowerConsumed", 0) or 0),
                        reverse=True,
                    )
                    balance_values = [point["production"] - point["consumption"] for point in state.history["power"]]
                    balance_now = balance_values[-1] if balance_values else 0.0
                    balance_color = "#f38ba8" if balance_now < 0 else "#a6e3a1"
                    balance_caption = "Consumption is outrunning output." if balance_now < 0 else "Output is staying ahead of consumption."
                    with ui.column().classes("w-full gap-4"):
                        with ui.row().classes("w-full gap-4 items-start"):
                            ui.html(
                                spark_chart(
                                    "Grid Load",
                                    f"Output versus consumption, with live reserve. {balance_caption}",
                                    [
                                        {"label": "Output", "values": [point["production"] for point in state.history["power"]], "color": "#89dceb", "fill": "#89dceb18"},
                                        {"label": "Consumption", "values": [point["consumption"] for point in state.history["power"]], "color": "#fab387", "fill": "#fab38716"},
                                        {"label": "Reserve", "values": balance_values, "color": balance_color, "fill": f"{balance_color}16"},
                                    ],
                                    formatter=format_power,
                                )
                            ).classes("w-full lg:w-7/12")
                            ui.html(
                                ranked_rows(
                                    "Top Consumers",
                                    "Highest live building draw from FRM power usage.",
                                    [
                                        {
                                            "label": entry.get("Name", "Machine"),
                                            "value": float((entry.get("PowerInfo") or {}).get("PowerConsumed", 0) or 0),
                                            "detail": entry.get("ClassName", ""),
                                        }
                                        for entry in consumers[:8]
                                    ],
                                    formatter=format_power,
                                    color="#fab387",
                                )
                            ).classes("w-full lg:w-5/12")
                        with ui.row().classes("w-full gap-4 items-start"):
                            for circuit in data.get("power", []):
                                margin = float(circuit.get("PowerProduction", 0) or 0) - float(circuit.get("PowerConsumed", 0) or 0)
                                level = "error" if circuit.get("FuseTriggered") or margin < 0 else "warn" if margin < 200 else "ok"
                                state_label = (
                                    "Fuse tripped"
                                    if circuit.get("FuseTriggered")
                                    else "Overdraw"
                                    if margin < 0
                                    else "Thin margin"
                                    if margin < 200
                                    else "Stable"
                                )
                                ui.html(
                                    f'<div class="frm-card">'
                                    f'<div style="display:flex;justify-content:space-between;gap:12px"><strong>Circuit Group {circuit.get("CircuitGroupID", 0)}</strong><span class="frm-status {tone(level)}">{state_label}</span></div>'
                                    f'<div class="frm-metric-grid" style="margin-top:12px">'
                                    f'<div class="frm-metric"><div class="frm-metric-label">Output</div><span class="frm-metric-value">{format_power(circuit.get("PowerProduction", 0))}</span></div>'
                                    f'<div class="frm-metric"><div class="frm-metric-label">Consumption</div><span class="frm-metric-value">{format_power(circuit.get("PowerConsumed", 0))}</span></div>'
                                    f'<div class="frm-metric"><div class="frm-metric-label">Reserve</div><span class="frm-metric-value">{format_power(margin)}</span></div>'
                                    f'<div class="frm-metric"><div class="frm-metric-label">Capacity</div><span class="frm-metric-value">{format_power(circuit.get("PowerCapacity", 0))}</span></div>'
                                    f'<div class="frm-metric"><div class="frm-metric-label">Battery</div><span class="frm-metric-value">{format_percent(circuit.get("BatteryPercent", 0))}</span></div>'
                                    f'</div></div>'
                                ).classes("w-full lg:w-[calc(50%-8px)]")

                render_power_summary()

                @ui.refreshable
                def render_switch_editor() -> None:
                    snapshot = current_snapshot()
                    mappings = current_mappings()
                    with ui.column().classes("w-full gap-3"):
                        if not snapshot.get("switches", []):
                            ui.label("No switches are available in the current FRM snapshot.").classes("frm-muted")
                        for power_switch in snapshot.get("switches", []):
                            default_name = power_switch.get("Name") or friendly_name(power_switch.get("ID"), power_switch.get("ID", "Switch"), mappings)
                            with ui.card().classes("frm-panel w-full"):
                                with ui.row().classes("w-full justify-between items-start"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(friendly_name(power_switch.get("ID"), default_name, mappings)).classes("text-lg font-bold")
                                        ui.label(power_switch.get("ClassName") or "").classes("frm-muted")
                                    ui.html(f'<span class="frm-status {tone("ok" if power_switch.get("IsOn") else "warn")}">{("On" if power_switch.get("IsOn") else "Off")}</span>')
                                with ui.row().classes("w-full gap-4 items-end"):
                                    name_input = ui.input("Switch name", value=power_switch.get("Name") or "").classes("w-full")
                                    priority_input = ui.number("Priority", value=power_switch.get("Priority", -1), min=-1, max=8, step=1)
                                ui.label(format_coords(power_switch.get("location"))).classes("frm-muted text-sm")
                                with ui.row().classes("gap-2"):
                                    ui.button(
                                        "Turn Off" if power_switch.get("IsOn") else "Turn On",
                                        on_click=lambda switch_id=power_switch.get("ID"), next_state=not bool(power_switch.get("IsOn")): asyncio.create_task(toggle_switch(switch_id, next_state)),
                                    )
                                    ui.button(
                                        "Save",
                                        on_click=lambda switch_id=power_switch.get("ID"), name_input=name_input, priority_input=priority_input: asyncio.create_task(save_switch_details(switch_id, str(name_input.value or ""), int(priority_input.value or -1))),
                                    )
                                    ui.button(
                                        "Pin Detail",
                                        on_click=lambda switch_id=power_switch.get("ID"), name=friendly_name(power_switch.get("ID"), default_name, mappings): asyncio.create_task(add_widget_to_dashboard(name, "switch_detail", {"object_id": switch_id})),
                                    )

                render_switch_editor()

            with ui.tab_panel(map_tab):
                with ui.row().classes("w-full gap-4"):
                    ui.checkbox("Players", value=True, on_change=lambda event: (page_state["map_layers"].__setitem__("players", bool(event.value)), render_map_view.refresh()))
                    ui.checkbox("Switches", value=True, on_change=lambda event: (page_state["map_layers"].__setitem__("switches", bool(event.value)), render_map_view.refresh()))
                    ui.checkbox("Markers", value=True, on_change=lambda event: (page_state["map_layers"].__setitem__("markers", bool(event.value)), render_map_view.refresh()))
                    ui.checkbox("Factory", value=False, on_change=lambda event: (page_state["map_layers"].__setitem__("factory", bool(event.value)), render_map_view.refresh()))

                @ui.refreshable
                def render_map_view() -> None:
                    snapshot = current_snapshot()
                    mapping_records = current_mappings()
                    mappings = {key: value.display_name for key, value in mapping_records.items()}
                    ui.html(map_html(snapshot, page_state["map_layers"], mappings)).classes("w-full")
                    with ui.row().classes("w-full gap-4 items-start"):
                        with ui.column().classes("w-full lg:w-6/12 gap-2"):
                            ui.label("Players").classes("text-lg font-bold")
                            if not snapshot.get("players", []):
                                ui.label("No players in the current snapshot.").classes("frm-muted")
                            for player in snapshot.get("players", [])[:8]:
                                ui.html(
                                    f'<div class="frm-row"><strong>{escape(friendly_name(player.get("ID"), player.get("Name", "Player"), mapping_records))}</strong>'
                                    f'<div class="frm-caption" style="margin-top:8px">{escape(format_coords(player.get("location")))}</div></div>'
                                )
                        with ui.column().classes("w-full lg:w-6/12 gap-2"):
                            ui.label("Markers").classes("text-lg font-bold")
                            if not snapshot.get("map_markers", []):
                                ui.label("No map markers in the current snapshot.").classes("frm-muted")
                            for marker in snapshot.get("map_markers", [])[:8]:
                                ui.html(
                                    f'<div class="frm-row"><strong>{escape(marker.get("Name") or marker.get("Category") or "Marker")}</strong>'
                                    f'<div class="frm-caption" style="margin-top:8px">{escape(format_coords(marker.get("location")))}</div></div>'
                                )

                render_map_view()

            with ui.tab_panel(automation_tab):
                with ui.row().classes("w-full gap-4 items-start"):
                    with ui.card().classes("frm-panel w-full"):
                        ui.label("Create Schedule Rule").classes("text-lg font-bold")
                        schedule_name = ui.input("Rule name", placeholder="Night backup grid").classes("w-full")
                        schedule_time = ui.input("Time (HH:MM)", value="18:00").classes("w-full")
                        schedule_timezone = ui.input("Timezone", value=config.default_schedule_timezone, placeholder="America/New_York or local").classes("w-full")
                        schedule_target_type = ui.select({"switch": "Switch", "factory": "Factory"}, value="switch", label="Target type")
                        schedule_target_id = ui.input("Target object ID", placeholder="Build_PriorityPowerSwitch_C_...").classes("w-full")
                        schedule_action = ui.select({True: "Turn on / enable", False: "Turn off / pause"}, value=True, label="Action")
                        schedule_cooldown = ui.number("Cooldown minutes", value=5, min=1, max=240, step=1)
                        ui.label("Days").classes("frm-muted")
                        day_boxes = {label: ui.checkbox(label, value=label in {"Mon", "Tue", "Wed", "Thu", "Fri"}) for label in DAY_OPTIONS}

                        def save_schedule_rule() -> None:
                            days = [DAY_OPTIONS[label] for label, checkbox in day_boxes.items() if checkbox.value]
                            target_type = str(schedule_target_type.value or "switch")
                            target_object_id = str(schedule_target_id.value or "").strip()
                            schedule_value = str(schedule_time.value or "").strip()
                            timezone_value = str(schedule_timezone.value or "").strip() or config.default_schedule_timezone
                            if not target_object_id:
                                ui.notify("A target object ID is required for schedule rules.", type="warning")
                                return
                            if not days:
                                ui.notify("Select at least one day for the schedule rule.", type="warning")
                                return
                            if not schedule_time_valid(schedule_value):
                                ui.notify("Schedule time must use HH:MM 24-hour format.", type="warning")
                                return
                            create_rule(
                                {
                                    "name": default_rule_name(str(schedule_name.value or ""), "schedule", target_type, target_object_id),
                                    "rule_type": "schedule",
                                    "enabled": True,
                                    "target_type": target_type,
                                    "target_object_id": target_object_id,
                                    "action_status": bool(schedule_action.value),
                                    "schedule_days": days,
                                    "schedule_time": schedule_value,
                                    "schedule_timezone": timezone_value,
                                    "cooldown_minutes": int(schedule_cooldown.value or 5),
                                    "source": "local",
                                }
                            )
                            render_rules_and_history.refresh()

                        ui.button("Create Schedule", on_click=save_schedule_rule)

                    with ui.card().classes("frm-panel w-full"):
                        ui.label("Create Threshold Rule").classes("text-lg font-bold")
                        threshold_name = ui.input("Rule name", placeholder="Low headroom start backup").classes("w-full")
                        threshold_metric = ui.select(RULE_METRICS, value="power.margin.min", label="Metric")
                        threshold_operator = ui.select({"<": "<", "<=": "<=", ">": ">", ">=": ">=", "==": "==", "!=": "!="}, value="<", label="Operator")
                        threshold_value = ui.number("Threshold", value=400, step=0.1)
                        threshold_match = ui.input("Item / match text", placeholder="Only for item rules").classes("w-full")
                        threshold_target_type = ui.select({"switch": "Switch", "factory": "Factory"}, value="switch", label="Target type")
                        threshold_target_id = ui.input("Target object ID", placeholder="Build_PriorityPowerSwitch_C_...").classes("w-full")
                        threshold_action = ui.select({True: "Turn on / enable", False: "Turn off / pause"}, value=True, label="Action")
                        threshold_cooldown = ui.number("Cooldown minutes", value=5, min=1, max=240, step=1)

                        def save_threshold_rule() -> None:
                            metric = str(threshold_metric.value or "")
                            target_type = str(threshold_target_type.value or "switch")
                            target_object_id = str(threshold_target_id.value or "").strip()
                            match_text = str(threshold_match.value or "").strip()
                            if not target_object_id:
                                ui.notify("A target object ID is required for threshold rules.", type="warning")
                                return
                            if metric.startswith("prod.item") and not match_text:
                                ui.notify("Item-based production rules need an item or class match value.", type="warning")
                                return
                            create_rule(
                                {
                                    "name": default_rule_name(str(threshold_name.value or ""), "threshold", target_type, target_object_id),
                                    "rule_type": "threshold",
                                    "enabled": True,
                                    "target_type": target_type,
                                    "target_object_id": target_object_id,
                                    "action_status": bool(threshold_action.value),
                                    "metric": metric,
                                    "operator": threshold_operator.value,
                                    "threshold": float(threshold_value.value or 0),
                                    "match_text": match_text,
                                    "cooldown_minutes": int(threshold_cooldown.value or 5),
                                    "source": "local",
                                }
                            )
                            render_rules_and_history.refresh()

                        ui.button("Create Trigger", on_click=save_threshold_rule)

                with ui.row().classes("w-full justify-end"):
                    ui.button("Sync Imported Rules", on_click=lambda: asyncio.create_task(sync_imported_rules_action()))

                @ui.refreshable
                def render_rules_and_history() -> None:
                    with SessionLocal() as session:
                        rules = list_rules(session)
                        events = list_events(session, limit=12)
                    with ui.row().classes("w-full gap-4 items-start"):
                        with ui.column().classes("w-full lg:w-7/12 gap-3"):
                            if not rules:
                                ui.label("No automation rules saved yet.").classes("frm-muted")
                            for rule in rules:
                                descriptor = (
                                    f'{day_labels(rule.schedule_days)} @ {rule.schedule_time} ({rule.schedule_timezone or "local"})'
                                    if rule.rule_type == "schedule"
                                    else f'{RULE_METRICS.get(rule.metric or "", rule.metric or "")} {rule.operator} {rule.threshold} {rule.match_text or ""}'
                                )
                                with ui.card().classes("frm-panel w-full"):
                                    with ui.row().classes("w-full justify-between items-start"):
                                        with ui.column().classes("gap-1"):
                                            ui.label(rule.name).classes("text-lg font-bold")
                                            ui.label(descriptor).classes("frm-muted")
                                            ui.label(f"{rule.target_type} -> {rule.target_object_id}").classes("frm-muted text-xs")
                                        ui.html(f'<span class="frm-status {tone("ok" if rule.enabled else "warn")}">{("Enabled" if rule.enabled else "Disabled")}</span>')
                                    with ui.row().classes("gap-2"):
                                        ui.button("Disable" if rule.enabled else "Enable", on_click=lambda rule_id=rule.id: toggle_rule_enabled(rule_id))
                                        ui.button("Run Now", on_click=lambda rule_id=rule.id: asyncio.create_task(run_rule(rule_id)))
                                        ui.button("Delete", on_click=lambda rule_id=rule.id: delete_rule(rule_id))
                                    ui.label(f"Last trigger: {rule.last_triggered_at.isoformat(timespec='seconds') if rule.last_triggered_at else 'Never'}").classes("frm-muted text-sm")
                        with ui.column().classes("w-full lg:w-5/12 gap-3"):
                            ui.label("Automation History").classes("text-lg font-bold")
                            if not events:
                                ui.label("No automation runs yet.").classes("frm-muted")
                            for event in events:
                                ui.html(
                                    f'<div class="frm-row"><div style="display:flex;justify-content:space-between;gap:12px"><strong>{escape(event.title)}</strong><span class="frm-status {tone(event.level)}">{escape(event.level)}</span></div><div class="frm-caption" style="margin-top:8px">{escape(event.detail)}</div></div>'
                                )

                render_rules_and_history()

            with ui.tab_panel(dashboard_tab):
                with ui.row().classes("w-full gap-4 items-end"):
                    dashboard_name = ui.input("Dashboard name", placeholder="Logistics wall").classes("w-full")
                    dashboard_description = ui.input("Description", placeholder="Optional description").classes("w-full")
                    ui.button("Create Dashboard", on_click=lambda: create_dashboard_action(str(dashboard_name.value or ""), str(dashboard_description.value or "")))

                with ui.row().classes("w-full gap-4 items-end"):
                    widget_picker = ui.select(WIDGET_CATALOG, value="session_pulse", label="Widget kind")
                    ui.button("Add Widget", on_click=lambda: asyncio.create_task(add_widget_to_dashboard(WIDGET_CATALOG.get(widget_picker.value, "Widget"), widget_picker.value, {})))

                @ui.refreshable
                def render_dashboard_view() -> None:
                    snapshot = current_snapshot()
                    mappings = current_mappings()
                    with SessionLocal() as session:
                        dashboards = list_dashboards(session)
                        events = list_events(session, limit=8)
                    if dashboards and page_state["dashboard_id"] is None:
                        page_state["dashboard_id"] = dashboards[0].id
                    active = next((dashboard for dashboard in dashboards if dashboard.id == page_state["dashboard_id"]), dashboards[0] if dashboards else None)

                    with ui.row().classes("w-full gap-4 items-start"):
                        with ui.column().classes("w-full lg:w-4/12 gap-3"):
                            if not dashboards:
                                ui.label("No dashboards created yet.").classes("frm-muted")
                            for dashboard in dashboards:
                                with ui.card().classes("frm-panel w-full"):
                                    with ui.row().classes("w-full justify-between items-start"):
                                        with ui.column().classes("gap-1"):
                                            ui.label(dashboard.name).classes("text-lg font-bold")
                                            ui.label(dashboard.description or "Custom dashboard").classes("frm-muted")
                                        ui.html(f'<span class="frm-status {tone("ok" if active and dashboard.id == active.id else "info")}">{("Active" if active and dashboard.id == active.id else "Idle")}</span>')
                                    with ui.row().classes("gap-2"):
                                        ui.button("Use", on_click=lambda dashboard_id=dashboard.id: (page_state.__setitem__("dashboard_id", dashboard_id), render_dashboard_view.refresh()))
                                        if len(dashboards) > 1:
                                            ui.button("Delete", on_click=lambda dashboard_id=dashboard.id: delete_dashboard_action(dashboard_id))
                        with ui.column().classes("w-full lg:w-8/12 gap-3"):
                            if active is None:
                                ui.label("No dashboard selected.").classes("frm-muted")
                            else:
                                ui.label(f"{active.name} Widgets").classes("text-lg font-bold")
                                if not active.widgets:
                                    ui.label("This dashboard does not have any widgets yet.").classes("frm-muted")
                                for widget in active.widgets:
                                    with ui.card().classes("frm-panel w-full"):
                                        with ui.row().classes("w-full justify-between items-start"):
                                            with ui.column().classes("gap-1"):
                                                ui.label(widget.title).classes("text-lg font-bold")
                                                ui.label(widget.widget_kind).classes("frm-muted")
                                            with ui.row().classes("gap-2"):
                                                ui.button("Up", on_click=lambda widget_id=widget.id: update_widget_layout(widget_id, -1))
                                                ui.button("Down", on_click=lambda widget_id=widget.id: update_widget_layout(widget_id, 1))
                                                ui.button("Remove", on_click=lambda widget_id=widget.id: delete_widget_action(widget_id))
                                        ui.html(widget_html(widget, snapshot, mappings, events)).classes("w-full")

                render_dashboard_view()

            with ui.tab_panel(settings_tab):
                with ui.card().classes("frm-panel w-full"):
                    ui.label("FRM Connection").classes("text-lg font-bold")
                    frm_base_url_input = ui.input("FRM Base URL", value=config.frm_base_url, placeholder="http://localhost:8080").classes("w-full")
                    frm_token_input = ui.input("FRM Token", value=config.frm_token, password=True, password_toggle_button=True).classes("w-full")
                    default_schedule_timezone_input = ui.input(
                        "Default schedule timezone",
                        value=config.default_schedule_timezone,
                        placeholder="America/New_York or local",
                    ).classes("w-full")
                    refresh_seconds_input = ui.number("Refresh seconds", value=config.refresh_seconds, min=5, max=300, step=1)
                    import_url_input = ui.input("Imported rule feed URL", value=config.schedule_import_url, placeholder="https://host/rules.json").classes("w-full")
                    import_refresh_input = ui.number("Import refresh minutes", value=config.import_refresh_minutes, min=1, max=1440, step=1)
                    ui.label("Use an IANA timezone like America/New_York. The value local follows the container TZ setting.").classes("frm-muted text-sm")
                    ui.button(
                        "Save Connection",
                        on_click=lambda: asyncio.create_task(
                            save_connection(
                                str(frm_base_url_input.value or ""),
                                str(frm_token_input.value or ""),
                                int(refresh_seconds_input.value or 10),
                                str(import_url_input.value or ""),
                                int(import_refresh_input.value or 5),
                                str(default_schedule_timezone_input.value or ""),
                            )
                        ),
                    )

                with ui.card().classes("frm-panel w-full"):
                    ui.label("Name Mappings").classes("text-lg font-bold")
                    mapping_object_id = ui.input("Object ID", placeholder="Build_PriorityPowerSwitch_C_...").classes("w-full")
                    mapping_category = ui.input("Category", value="general").classes("w-full")
                    mapping_display_name = ui.input("Display name", placeholder="Backup Grid A").classes("w-full")
                    mapping_notes = ui.textarea("Notes", placeholder="Optional operator notes").classes("w-full")
                    ui.button(
                        "Save Mapping",
                        on_click=lambda: save_name_mapping(
                            str(mapping_object_id.value or ""),
                            str(mapping_category.value or ""),
                            str(mapping_display_name.value or ""),
                            str(mapping_notes.value or ""),
                        ),
                    )

                @ui.refreshable
                def render_settings_lists() -> None:
                    with SessionLocal() as session:
                        mappings = list_name_mappings(session)
                    with ui.column().classes("w-full gap-3"):
                        if not mappings:
                            ui.label("No custom name mappings saved yet.").classes("frm-muted")
                        for mapping in mappings:
                            with ui.card().classes("frm-panel w-full"):
                                with ui.row().classes("w-full justify-between items-start"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(mapping.display_name).classes("text-lg font-bold")
                                        ui.label(mapping.object_id).classes("frm-muted")
                                        ui.label(mapping.category).classes("frm-muted text-xs")
                                    ui.button("Delete", on_click=lambda mapping_id=mapping.id: delete_mapping(mapping_id))
                                if mapping.notes:
                                    ui.label(mapping.notes).classes("frm-muted")

                render_settings_lists()

        ui.timer(6.0, refresh_dynamic_sections)


def main() -> None:
    ui.run(title=settings.app_title, host=settings.host, port=settings.port, reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
