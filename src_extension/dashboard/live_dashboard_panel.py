"""Live Mesa TextElement panel for read-only dashboard state.

Renders model.get_dashboard_state() as a styled HTML status board. This module is
purely presentational: render() only READS the dashboard state and never mutates the
model. Any error is caught and reported inline so a render failure cannot break the
Mesa browser refresh.
"""

from __future__ import annotations

import html
from typing import Any

from mesa.visualization.ModularVisualization import TextElement


# ---- small formatting helpers -------------------------------------------------

def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _fmt_pos(pos: Any) -> str:
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        try:
            return f"({int(round(float(pos[0])))}, {int(round(float(pos[1])))})"
        except (TypeError, ValueError):
            return f"({pos[0]}, {pos[1]})"
    if pos in (None, ""):
        return "&mdash;"
    return _esc(pos)


def _fmt_num(value: Any, nd: int = 0) -> str:
    try:
        if nd == 0:
            return str(int(round(float(value))))
        return f"{float(value):.{nd}f}"
    except (TypeError, ValueError):
        return _esc(value)


# ---- color palette ------------------------------------------------------------

_C = {
    "bg": "#0f1419",
    "card": "#1a2129",
    "card2": "#232d38",
    "line": "#2f3b47",
    "text": "#d8dee6",
    "muted": "#8a97a5",
    "accent": "#4aa3ff",
    "green": "#3ecf8e",
    "amber": "#f5a623",
    "red": "#ff5a5a",
    "purple": "#b07cff",
    "teal": "#22c3c3",
}

_SEVERITY_COLOR = {"critical": _C["red"], "warning": _C["amber"], "info": _C["accent"]}
_STATUS_COLOR = {
    "rescued": _C["green"],
    "available": _C["green"],
    "dead": _C["red"],
    "cancelled": _C["red"],
    "candidate": _C["amber"],
    "assigned": _C["accent"],
    "detected": _C["accent"],
    "unreachable": _C["muted"],
}


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='display:inline-block;padding:1px 7px;border-radius:10px;"
        f"background:{color}22;color:{color};border:1px solid {color}55;"
        f"font-size:11px;font-weight:600;white-space:nowrap'>{_esc(text)}</span>"
    )


def _status_badge(status: Any) -> str:
    s = str(status or "").lower()
    return _badge(status or "?", _STATUS_COLOR.get(s, _C["muted"]))


def _bool_badge(value: Any, true_color: str = None, false_color: str = None) -> str:
    truthy = bool(value)
    color = (true_color or _C["green"]) if truthy else (false_color or _C["muted"])
    return _badge("yes" if truthy else "no", color)


class DashboardPanel(TextElement):
    """Styled HTML status board; reads ``model.get_dashboard_state()`` only."""

    def render(self, model) -> str:
        try:
            if not hasattr(model, "get_dashboard_state"):
                return self._error("get_dashboard_state unavailable")
            state = model.get_dashboard_state()
            if not isinstance(state, dict):
                return self._error("invalid dashboard state")
            return self._format_state(state)
        except Exception as exc:  # never raise from render(): would break the refresh
            return self._error(_esc(exc))

    # -- top-level layout -------------------------------------------------------

    def _format_state(self, state: dict[str, Any]) -> str:
        mission = state.get("mission_status") or {}
        fire = state.get("fire_view") or {}
        comm = state.get("communication_view") or {}
        failsafe = state.get("fail_safe_view") or {}

        css = (
            f"font-family:'Segoe UI',system-ui,sans-serif;color:{_C['text']};"
            f"background:{_C['bg']};padding:14px 16px;border-radius:12px;"
            f"max-width:760px;line-height:1.5;font-size:13px;"
            f"box-shadow:0 2px 12px rgba(0,0,0,.35)"
        )
        out = [f"<div style=\"{css}\">"]
        out.append(self._header(state, mission))
        out.append(self._mission_strip(mission, fire))
        out.append("<div style='display:flex;gap:12px;flex-wrap:wrap;margin-top:12px'>")
        out.append(self._fire_card(fire))
        out.append(self._comm_card(comm))
        out.append(self._failsafe_card(failsafe, state))
        out.append("</div>")
        out.append(self._uav_card(state.get("uav_status_view") or []))
        out.append(self._victim_card(state.get("victim_view") or []))
        out.append(self._firefighter_card(state.get("firefighter_view") or []))
        out.append(self._alerts_card(state))
        out.append(self._timeline_card(state.get("timeline") or []))
        out.append("</div>")
        return "".join(out)

    # -- building blocks --------------------------------------------------------

    def _header(self, state: dict, mission: dict) -> str:
        step = state.get("step", "?")
        mode = mission.get("mission_mode", "?")
        mode_color = _C["amber"] if "recovery" in str(mode) else _C["green"]
        return (
            "<div style='display:flex;align-items:center;justify-content:space-between;"
            f"border-bottom:1px solid {_C['line']};padding-bottom:8px;margin-bottom:10px'>"
            f"<span style='font-size:16px;font-weight:700;color:{_C['text']}'>"
            f"\U0001f6f0 Mission Dashboard</span>"
            f"<span style='font-size:12px;color:{_C['muted']}'>step "
            f"<b style='color:{_C['accent']};font-size:15px'>{_esc(step)}</b> / "
            f"{_esc(mission.get('batch_size', '?'))} &nbsp; {_badge(mode, mode_color)}</span>"
            "</div>"
        )

    def _mission_strip(self, mission: dict, fire: dict) -> str:
        rescued = int(mission.get("rescued_count", 0) or 0)
        dead = int(mission.get("dead_victim_count", 0) or 0)
        unresolved = int(mission.get("unresolved_victim_count", 0) or 0)
        total = max(rescued + dead + unresolved, 1)
        terminal = mission.get("all_victims_terminal", False)

        def seg(count, color):
            if count <= 0:
                return ""
            pct = 100.0 * count / total
            return f"<div style='width:{pct:.1f}%;background:{color};height:100%'></div>"

        bar = (
            "<div style='display:flex;height:10px;border-radius:5px;overflow:hidden;"
            f"background:{_C['card2']};margin:6px 0'>"
            + seg(rescued, _C["green"]) + seg(dead, _C["red"]) + seg(unresolved, _C["amber"])
            + "</div>"
        )
        stats = (
            "<div style='display:flex;gap:14px;font-size:12px'>"
            f"<span>{_badge('rescued ' + str(rescued), _C['green'])}</span>"
            f"<span>{_badge('dead ' + str(dead), _C['red'])}</span>"
            f"<span>{_badge('unresolved ' + str(unresolved), _C['amber'])}</span>"
            f"<span style='margin-left:auto'>all terminal "
            f"{_bool_badge(terminal)}</span>"
            "</div>"
        )
        return f"<div>{bar}{stats}</div>"

    def _stat_card(self, title: str, rows_html: str, accent: str) -> str:
        return (
            f"<div style='flex:1;min-width:210px;background:{_C['card']};"
            f"border:1px solid {_C['line']};border-left:3px solid {accent};"
            "border-radius:8px;padding:9px 11px'>"
            f"<div style='font-weight:700;color:{accent};font-size:12px;"
            f"text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px'>{_esc(title)}</div>"
            f"{rows_html}</div>"
        )

    def _kv(self, key: str, value_html: str) -> str:
        return (
            f"<div style='display:flex;justify-content:space-between;gap:8px;font-size:12px'>"
            f"<span style='color:{_C['muted']}'>{_esc(key)}</span>"
            f"<span style='text-align:right'>{value_html}</span></div>"
        )

    def _fire_card(self, fire: dict) -> str:
        wv = fire.get("wind_vector", [])
        wv_txt = f"({wv[0]}, {wv[1]})" if isinstance(wv, (list, tuple)) and len(wv) >= 2 else _esc(wv)
        rows = (
            self._kv("active fire", f"<b style='color:{_C['red']}'>{_fmt_num(fire.get('active_fire_cells', 0))}</b>")
            + self._kv("smoke", f"<span style='color:{_C['muted']}'>{_fmt_num(fire.get('active_smoke_cells', 0))}</span>")
            + self._kv("burnt", f"<b style='color:{_C['amber']}'>{_fmt_num(fire.get('burnt_cells', 0))}</b>")
            + self._kv("ever burned", _fmt_num(fire.get("has_burned_cells", 0)))
            + self._kv("wind", f"{_badge(fire.get('wind_direction', '?'), _C['teal'])} {_esc(wv_txt)}")
        )
        return self._stat_card("Fire", rows, _C["red"])

    def _comm_card(self, comm: dict) -> str:
        conf = comm.get("delivery_confidence")
        conf_color = _C["green"] if (conf or 0) >= 0.75 else (_C["amber"] if (conf or 0) >= 0.5 else _C["red"])
        rows = (
            self._kv("mode", _badge(comm.get("communication_mode", "?"), _C["accent"]))
            + self._kv("delivery conf", f"<b style='color:{conf_color}'>{_fmt_num(conf, 2)}</b>")
            + self._kv("msg load", _fmt_num(comm.get("message_load", 0)))
            + self._kv("relay needed", _bool_badge(comm.get("relay_needed"), _C["amber"], _C["green"]))
        )
        return self._stat_card("Comms", rows, _C["accent"])

    def _failsafe_card(self, failsafe: dict, state: dict) -> str:
        mode = failsafe.get("current_mode", "?")
        mode_color = _C["amber"] if "recovery" in str(mode) else _C["green"]
        triggers = failsafe.get("active_triggers") or []
        uniq = []
        for t in triggers:
            if t not in uniq:
                uniq.append(t)
        trig_html = " ".join(_badge(t.lower(), _C["purple"]) for t in uniq[:4]) or f"<span style='color:{_C['muted']}'>none</span>"
        rows = (
            self._kv("mode", _badge(mode, mode_color))
            + self._kv("critical alerts", f"<b style='color:{_C['red']}'>{_esc(state.get('critical_alert_count', 0))}</b>")
            + self._kv("option cmp", _esc(state.get("option_comparison_count", 0)))
            + f"<div style='margin-top:5px;display:flex;gap:4px;flex-wrap:wrap'>{trig_html}</div>"
        )
        return self._stat_card("Fail-safe", rows, _C["amber"])

    # -- entity tables ----------------------------------------------------------

    def _table(self, headers: list[str], rows: list[str], accent: str, title: str) -> str:
        thead = "".join(
            f"<th style='text-align:left;padding:4px 8px;color:{_C['muted']};"
            f"font-size:11px;text-transform:uppercase;letter-spacing:.4px;"
            f"border-bottom:1px solid {_C['line']}'>{_esc(h)}</th>"
            for h in headers
        )
        body = "".join(rows)
        return (
            f"<div style='margin-top:12px'>"
            f"<div style='font-weight:700;color:{accent};font-size:12px;"
            f"text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px'>{_esc(title)}</div>"
            f"<table style='width:100%;border-collapse:collapse;background:{_C['card']};"
            f"border:1px solid {_C['line']};border-radius:8px;overflow:hidden'>"
            f"<tr>{thead}</tr>{body}</table></div>"
        )

    def _td(self, content: str) -> str:
        return f"<td style='padding:4px 8px;font-size:12px;border-bottom:1px solid {_C['line']}22'>{content}</td>"

    def _uav_card(self, uavs: list[dict]) -> str:
        if not uavs:
            return ""
        rows = []
        for u in uavs:
            role = str(u.get("role", ""))
            role_color = _C["teal"] if "tracker" in role else _C["purple"]
            batt = u.get("battery", 0) or 0
            batt_color = _C["green"] if batt >= 50 else (_C["amber"] if batt >= 20 else _C["red"])
            rows.append(
                "<tr>"
                + self._td(f"<b style='color:{_C['accent']}'>{_esc(u.get('id', ''))}</b>")
                + self._td(_badge(role, role_color))
                + self._td(_fmt_pos(u.get("position")))
                + self._td(f"<span style='color:{_C['muted']}'>{_esc(u.get('execution_action', ''))}</span>")
                + self._td(_fmt_pos(u.get("target_position")))
                + self._td(f"<b style='color:{batt_color}'>{_fmt_num(batt)}%</b>")
                + "</tr>"
            )
        return self._table(["uav", "role", "pos", "action", "target", "batt"], rows, _C["teal"], "UAVs")

    def _victim_card(self, victims: list[dict]) -> str:
        if not victims:
            return ""
        rows = []
        for v in victims:
            rows.append(
                "<tr>"
                + self._td(f"<b>{_esc(v.get('id', ''))}</b>")
                + self._td(_fmt_pos(v.get("position")))
                + self._td(_status_badge(v.get("status")))
                + self._td(_bool_badge(v.get("detected"), _C["accent"], _C["muted"]))
                + self._td(_esc(v.get("assigned_firefighter")) if v.get("assigned_firefighter") else "&mdash;")
                + "</tr>"
            )
        return self._table(["victim", "pos", "status", "detected", "assigned ff"], rows, _C["green"], "Victims")

    def _firefighter_card(self, ffs: list[dict]) -> str:
        if not ffs:
            return ""
        rows = []
        for f in ffs:
            alive = f.get("alive", True)
            rows.append(
                "<tr>"
                + self._td(f"<b>{_esc(f.get('id', ''))}</b>")
                + self._td(_fmt_pos(f.get("position")))
                + self._td(_badge("alive", _C["green"]) if alive else _badge("dead", _C["red"]))
                + self._td(_bool_badge(f.get("assigned"), _C["accent"], _C["muted"]))
                + self._td(_bool_badge(f.get("route_blocked"), _C["red"], _C["green"]))
                + self._td(_status_badge(f.get("status")))
                + "</tr>"
            )
        return self._table(["unit", "pos", "alive", "assigned", "blocked", "status"], rows, _C["amber"], "Firefighters")

    def _alerts_card(self, state: dict) -> str:
        alerts = list(state.get("alert_list") or [])[-5:]
        if not alerts:
            return ""
        items = []
        for a in reversed(alerts):
            sev = str(a.get("severity", "info")).lower()
            color = _SEVERITY_COLOR.get(sev, _C["accent"])
            items.append(
                f"<li style='margin:3px 0;list-style:none;display:flex;gap:8px;align-items:baseline'>"
                f"{_badge(sev, color)}"
                f"<span style='color:{_C['muted']};font-size:11px'>s{_esc(a.get('step', ''))}</span>"
                f"<span><b>{_esc(a.get('alert_type', ''))}</b> "
                f"<span style='color:{_C['muted']}'>{_esc(a.get('message', ''))}</span></span></li>"
            )
        return (
            f"<div style='margin-top:12px'><div style='font-weight:700;color:{_C['red']};"
            "font-size:12px;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px'>"
            f"Recent Alerts <span style='color:{_C['muted']};font-weight:400'>"
            f"(crit {state.get('critical_alert_count',0)} / warn {state.get('warning_alert_count',0)} / "
            f"info {state.get('info_alert_count',0)})</span></div>"
            f"<ul style='margin:0;padding:0'>{''.join(items)}</ul></div>"
        )

    def _timeline_card(self, timeline: list[dict]) -> str:
        events = list(timeline)[-5:]
        if not events:
            return ""
        items = []
        for e in reversed(events):
            items.append(
                f"<li style='margin:3px 0;list-style:none;display:flex;gap:8px;align-items:baseline'>"
                f"<span style='color:{_C['accent']};font-size:11px;font-weight:600;"
                f"min-width:34px'>s{_esc(e.get('step', ''))}</span>"
                f"<span><b style='color:{_C['teal']}'>{_esc(e.get('event_type', ''))}</b> "
                f"<span style='color:{_C['muted']}'>{_esc(e.get('entity_id', ''))} "
                f"&middot; {_esc(e.get('message', ''))}</span></span></li>"
            )
        return (
            f"<div style='margin-top:12px'><div style='font-weight:700;color:{_C['teal']};"
            "font-size:12px;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px'>"
            "Mission Timeline</div>"
            f"<ul style='margin:0;padding:0'>{''.join(items)}</ul></div>"
        )

    def _error(self, msg: str) -> str:
        return (
            f"<div style='font-family:sans-serif;color:{_C['red']};background:{_C['card']};"
            f"padding:10px;border-radius:8px;border:1px solid {_C['red']}55'>"
            f"<b>Dashboard unavailable:</b> {msg}</div>"
        )
