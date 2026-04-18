from __future__ import annotations

from html import escape
from typing import Iterable


def format_number(value: float | int | None, digits: int = 0) -> str:
    number = float(value or 0)
    return f"{number:,.{digits}f}"


def format_compact(value: float | int | None) -> str:
    number = float(value or 0)
    magnitude = abs(number)
    if magnitude >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if magnitude >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if magnitude >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:.0f}"


def format_power(value: float | int | None) -> str:
    number = float(value or 0)
    return f"{number:.1f} MW"


def format_rate(value: float | int | None) -> str:
    number = float(value or 0)
    return f"{number:.1f}/min"


def format_percent(value: float | int | None) -> str:
    number = float(value or 0)
    return f"{number:.1f}%"


def format_coords(location: dict | None) -> str:
    if not location:
        return "No coordinates"
    return (
        f"X {format_number(location.get('x', 0))} | "
        f"Y {format_number(location.get('y', 0))} | "
        f"Z {format_number(location.get('z', 0))}"
    )


def tone(level: str) -> str:
    if level == "ok":
        return "frm-ok"
    if level == "warn":
        return "frm-warn"
    if level == "error":
        return "frm-error"
    return "frm-info"


def summary(snapshot: dict) -> dict:
    power = snapshot.get("power", [])
    factory = snapshot.get("factory", [])
    players = snapshot.get("players", [])
    switches = snapshot.get("switches", [])
    return {
        "power_production": sum(float(circuit.get("PowerProduction", 0) or 0) for circuit in power),
        "power_consumption": sum(float(circuit.get("PowerConsumed", 0) or 0) for circuit in power),
        "power_capacity": sum(float(circuit.get("PowerCapacity", 0) or 0) for circuit in power),
        "active_players": sum(1 for player in players if player.get("Online")),
        "paused_factories": sum(1 for machine in factory if machine.get("IsPaused")),
        "producing_factories": sum(1 for machine in factory if machine.get("IsProducing")),
        "switches_off": sum(1 for switch in switches if not switch.get("IsOn")),
        "triggered_fuses": sum(1 for circuit in power if circuit.get("FuseTriggered")),
        "avg_utilization": (
            sum(float((machine.get("production") or [{}])[0].get("ProdPercent", 0) or 0) for machine in factory if machine.get("production"))
            / max(sum(1 for machine in factory if machine.get("production")), 1)
        ),
    }


def alerts(snapshot: dict) -> list[dict]:
    info = summary(snapshot)
    margin = info["power_production"] - info["power_consumption"]
    results: list[dict] = []
    if margin < 0:
        results.append({"level": "error", "title": "Power deficit", "detail": f"{format_power(abs(margin))} short right now."})
    elif margin < 400:
        results.append({"level": "warn", "title": "Thin power margin", "detail": f"Only {format_power(margin)} of live headroom."})
    if info["triggered_fuses"] > 0:
        results.append({"level": "error", "title": "Fuse trips detected", "detail": f"{info['triggered_fuses']} circuits have a tripped fuse."})
    if info["switches_off"] > 0:
        results.append({"level": "warn", "title": "Switches offline", "detail": f"{info['switches_off']} switches are currently off."})
    if info["paused_factories"] > 0:
        results.append({"level": "info", "title": "Paused buildings", "detail": f"{info['paused_factories']} factory buildings are paused."})
    if not results:
        results.append({"level": "ok", "title": "Systems clean", "detail": "No high-signal issues detected in the current FRM snapshot."})
    return results


def points(values: list[float], width: int, height: int, minimum: float, maximum: float) -> str:
    if not values:
        return ""
    usable_height = height - 34
    usable_width = width - 30
    span = maximum - minimum or 1
    coords: list[str] = []
    for index, value in enumerate(values):
        x = 15 + (usable_width * index) / max(len(values) - 1, 1)
        y = 15 + usable_height - ((value - minimum) / span) * usable_height
        coords.append(f"{x},{y}")
    return " ".join(coords)


def spark_chart(title: str, caption: str, series: list[dict], formatter=format_number) -> str:
    width = 620
    height = 220
    values = [point for entry in series for point in entry["values"]]
    if not values:
        return '<div class="frm-card"><div class="frm-caption">No live samples yet.</div></div>'
    minimum = min(values)
    maximum = max(values)
    chart_max = maximum if maximum != minimum else maximum + 1
    guides = [minimum, minimum + (chart_max - minimum) / 2, chart_max]
    guide_lines = []
    for value in guides:
        y = 15 + (height - 34) - ((value - minimum) / (chart_max - minimum or 1)) * (height - 34)
        guide_lines.append(
            f'<line x1="15" y1="{y}" x2="{width - 15}" y2="{y}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="5 7" />'
            f'<text x="{width - 8}" y="{y - 6}" text-anchor="end" fill="rgba(255,255,255,0.55)" font-size="12">{escape(formatter(value))}</text>'
        )
    lines = []
    legend = []
    for entry in series:
        polyline = points(entry["values"], width, height, minimum, chart_max)
        lines.append(
            f'<polyline fill="none" stroke="{entry["color"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="{polyline}" />'
        )
        legend.append(
            f'<span class="frm-chip" style="color:{entry["color"]};border:1px solid {entry["color"]}22;background:{entry.get("fill", entry["color"] + "12")}">{escape(entry["label"])} {escape(formatter(entry["values"][-1] if entry["values"] else 0))}</span>'
        )
    return (
        f'<div class="frm-card frm-chart">'
        f'<div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">'
        f'<div><div style="font-weight:700">{escape(title)}</div><div class="frm-caption">{escape(caption)}</div></div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:8px">{"".join(legend)}</div></div>'
        f'<svg viewBox="0 0 {width} {height}">{"".join(guide_lines)}{"".join(lines)}</svg>'
        f'</div>'
    )


def ranked_rows(title: str, subtitle: str, items: Iterable[dict], formatter=format_number, color: str = "#50d6c2") -> str:
    rows = []
    ranked = list(items)
    if not ranked:
        return '<div class="frm-card"><div class="frm-caption">Nothing to show yet.</div></div>'
    maximum = max(float(item["value"]) for item in ranked) or 1.0
    for item in ranked[:7]:
        percent = min(max((float(item["value"]) / maximum) * 100, 0), 100)
        rows.append(
            f'<div class="frm-row">'
            f'<div style="display:flex;justify-content:space-between;gap:12px"><strong>{escape(item["label"])}</strong><span class="frm-muted">{escape(formatter(item["value"]))}</span></div>'
            f'<div class="frm-bar" style="margin-top:10px"><span style="width:{percent}%;background:linear-gradient(90deg,{color},rgba(255,255,255,0.85))"></span></div>'
            f'<div class="frm-caption" style="margin-top:8px">{escape(item.get("detail", ""))}</div>'
            f'</div>'
        )
    return (
        f'<div class="frm-card">'
        f'<div style="font-weight:700">{escape(title)}</div>'
        f'<div class="frm-caption" style="margin-bottom:12px">{escape(subtitle)}</div>'
        f'{"".join(rows)}'
        f'</div>'
    )


def map_html(snapshot: dict, layers: dict[str, bool], mappings: dict[str, str]) -> str:
    colors = {"players": "#78b7ff", "switches": "#ffb14d", "markers": "#50d6c2", "factory": "#a9f06c"}
    entities: list[dict] = []
    if layers.get("players", True):
        entities.extend(
            {"id": entry.get("ID"), "label": mappings.get(entry.get("ID"), entry.get("Name", "Player")), "type": "players", "location": entry.get("location")}
            for entry in snapshot.get("players", [])
        )
    if layers.get("switches", True):
        entities.extend(
            {"id": entry.get("ID"), "label": mappings.get(entry.get("ID"), entry.get("Name") or entry.get("SwitchTag") or entry.get("ID", "Switch")), "type": "switches", "location": entry.get("location")}
            for entry in snapshot.get("switches", [])
        )
    if layers.get("markers", True):
        entities.extend(
            {"id": entry.get("ID"), "label": entry.get("Name") or entry.get("Category") or "Marker", "type": "markers", "location": entry.get("location")}
            for entry in snapshot.get("map_markers", [])
        )
    if layers.get("factory", False):
        entities.extend(
            {"id": entry.get("ID"), "label": mappings.get(entry.get("ID"), entry.get("Name", "Machine")), "type": "factory", "location": entry.get("location")}
            for entry in snapshot.get("factory", [])[:300]
        )
    entities = [entity for entity in entities if entity.get("location")]
    if entities:
        xs = [float(entity["location"].get("x", 0) or 0) for entity in entities]
        ys = [float(entity["location"].get("y", 0) or 0) for entity in entities]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad_x = max((max_x - min_x) * 0.12, 9000)
        pad_y = max((max_y - min_y) * 0.12, 9000)
        bounds = {"min_x": min_x - pad_x, "max_x": max_x + pad_x, "min_y": min_y - pad_y, "max_y": max_y + pad_y}
    else:
        bounds = {"min_x": -400000, "max_x": 400000, "min_y": -400000, "max_y": 400000}

    def project(location: dict) -> tuple[float, float]:
        width, height = 1000, 720
        nx = (float(location.get("x", 0) or 0) - bounds["min_x"]) / (bounds["max_x"] - bounds["min_x"] or 1)
        ny = (float(location.get("y", 0) or 0) - bounds["min_y"]) / (bounds["max_y"] - bounds["min_y"] or 1)
        return 52 + nx * (width - 104), height - 52 - ny * (height - 104)

    grid_lines = []
    for index in range(6):
        ratio = index / 5
        x = 52 + ratio * 896
        y = 52 + ratio * 616
        grid_lines.append(f'<line x1="{x}" y1="52" x2="{x}" y2="668" stroke="rgba(255,255,255,0.07)" stroke-dasharray="8 12" />')
        grid_lines.append(f'<line x1="52" y1="{y}" x2="948" y2="{y}" stroke="rgba(255,255,255,0.07)" stroke-dasharray="8 12" />')

    plots = []
    for entity in entities:
        x, y = project(entity["location"])
        color = colors[entity["type"]]
        radius = 3.8 if entity["type"] == "factory" else 5.5
        plots.append(
            f'<circle cx="{x}" cy="{y}" r="{radius + 10}" fill="{color}18" />'
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" stroke="{color}55" stroke-width="1.5">'
            f'<title>{escape(entity["label"])}</title></circle>'
        )

    legend = "".join(
        f'<span class="frm-chip" style="color:{color};border:1px solid {color}24;background:{color}12">{label}</span>'
        for label, color in [("Players", colors["players"]), ("Switches", colors["switches"]), ("Markers", colors["markers"]), ("Factory", colors["factory"])]
    )

    return (
        f'<div class="frm-card frm-map">'
        f'<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start">'
        f'<div><div style="font-weight:700">Factory Atlas</div><div class="frm-caption">Players, switches, markers, and optional machine layer in one coordinate space.</div></div>'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap">{legend}</div></div>'
        f'<svg viewBox="0 0 1000 720">'
        f'<rect x="30" y="30" width="940" height="660" rx="28" fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.08)" />'
        f'<circle cx="310" cy="160" r="220" fill="rgba(255,255,255,0.04)" />'
        f'<circle cx="800" cy="560" r="180" fill="rgba(255,255,255,0.03)" />'
        f'{"".join(grid_lines)}'
        f'<text x="58" y="46" fill="rgba(255,255,255,0.52)" font-size="13">North</text>'
        f'<text x="58" y="702" fill="rgba(255,255,255,0.42)" font-size="12">Bounds X {escape(format_number(bounds["min_x"]))} to {escape(format_number(bounds["max_x"]))} | Y {escape(format_number(bounds["min_y"]))} to {escape(format_number(bounds["max_y"]))}</text>'
        f'{"".join(plots)}'
        f'</svg></div>'
    )
