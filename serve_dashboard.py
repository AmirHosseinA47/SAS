"""Live interactive dashboard launcher for Wildfire-UAVSim.

Run from the project root:
    python serve_dashboard.py
    (or it is launched automatically by `python main.py`)

Then open http://localhost:8000.

The simulation runs LIVE and in ONE phase: the moment you press Run, the model is
built and the map + all panels appear immediately, updating after every step as the
real WildFireModel advances. Start/Pause/Step/Reset control it, exactly like a live
viewer. A post-mission evaluation appears when all victims reach a terminal state or
the step limit is hit.

Read-only with respect to simulation logic: it only runs the existing model and reads
state; it changes no behavior.
"""
from __future__ import annotations

import json
import os
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

os.environ.setdefault("MPLBACKEND", "Agg")

import common_fixed_variables as cfv
import wildfire_model as wf
import agents as am
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

PORT = 8000

BUILTIN_SCENARIOS = {
    "A": {"label": "A - Rescue Success", "NUM_AGENTS": 3, "NUM_VICTIMS": 5, "NUM_FIREFIGHTERS": 3},
    "B": {"label": "B - Battery Fail-Safe", "NUM_AGENTS": 3, "NUM_VICTIMS": 2, "NUM_FIREFIGHTERS": 2},
    "C": {"label": "C - Large Operation", "NUM_AGENTS": 5, "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 3},
    "D": {"label": "D - Rescue Priority", "NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2},
}

VEG = set(cfv.VEGETATION_COLORS)
_lock = threading.Lock()
SESSION: dict = {"model": None, "step": 0, "steps": 0, "params": None,
                 "terminal_step": None, "finished": False}


def _veg_color(fuel):
    return cfv.VEGETATION_COLORS[cfv.normalize_fuel_values(fuel, cfv.FUEL_UPPER_LIMIT)]


def _fire_color(fuel):
    return cfv.FIRE_COLORS[cfv.normalize_fuel_values(fuel, cfv.FUEL_UPPER_LIMIT)]


def _cell_color(c):
    if c.smoke.is_smoke_active():
        return cfv.SMOKE_COLORS[0]
    if c.is_burning():
        return _fire_color(c.get_fuel())
    if c.is_burnt() or getattr(c, "has_burned", False):
        return "#2b2b2b"
    return _veg_color(c.get_fuel())


def _role_color(role):
    return {"victim_searcher": "#00FFFF", "fire_tracker": "#FF00FF", "relay": "#0066CC",
            "victim_confirmer": "#FF8C00", "return_to_base": "#888888"}.get(role, "#000000")


def _victim_color(status):
    return {"candidate": "#FFFF00", "confirmed": "#FFA500", "assigned": "#00AAFF",
            "rescued": "#00AAFF", "dead": "#000000"}.get(status, "#FFFF00")


def _slim_panel(p):
    cv = p.get("communication_view", {}) or {}
    fs = p.get("fail_safe_view", {}) or {}
    return {
        "step": p.get("step"),
        "mission_status": p.get("mission_status"),
        "fire_view": p.get("fire_view"),
        "communication_view": {k: cv.get(k) for k in
                               ["communication_mode", "delivery_confidence", "message_load", "relay_needed"]},
        "fail_safe_view": {"current_mode": fs.get("current_mode"), "active_triggers": fs.get("active_triggers", [])},
        "uav_status_view": [{k: u.get(k) for k in
                             ["id", "role", "position", "battery", "execution_action", "target_position"]}
                            for u in p.get("uav_status_view", [])],
        "victim_view": [{k: v.get(k) for k in ["id", "position", "status", "detected", "assigned_firefighter"]}
                        for v in p.get("victim_view", [])],
        "firefighter_view": [{k: f.get(k) for k in ["id", "position", "alive", "assigned", "route_blocked", "status"]}
                             for f in p.get("firefighter_view", [])],
        "alert_list": [{k: a.get(k) for k in ["step", "severity", "alert_type", "target_id", "message"]}
                       for a in p.get("alert_list", [])[-8:]],
        "timeline": [{k: e.get(k) for k in ["step", "event_type", "entity_id", "message"]}
                     for e in p.get("timeline", [])[-25:]],
        "critical_alert_count": p.get("critical_alert_count"),
        "warning_alert_count": p.get("warning_alert_count"),
        "info_alert_count": p.get("info_alert_count"),
        "option_comparison_count": p.get("option_comparison_count"),
    }


def _capture_frame(model, step):
    st = model.get_dashboard_state()
    cells, prob = {}, {}
    fire_cells = {}
    for c in model.schedule.agents:
        if type(c).__name__ != "Fire":
            continue
        x, y = int(c.pos[0]), int(c.pos[1])
        fire_cells[(x, y)] = c
        col = _cell_color(c)
        # Send every cell's colour, including plain vegetation, so the varied fuel-based
        # greens render as a jungle (different green per fuel level) instead of one flat
        # background. Non-veg cells (fire/smoke/charred) were already sent before.
        cells["%d,%d" % (x, y)] = col
        try:
            pv = float(c.get_prob())
            if pv >= 0.12:
                prob["%d,%d" % (x, y)] = round(pv, 2)
        except Exception:
            pass

    # Spared-vegetation muting: unburnt vegetation cells that are surrounded by burnt /
    # charred ground are genuine unburnt pockets (the stochastic fire skipped them). They
    # are not a bug, but rendered as bright green they look out of place inside the burn
    # scar, so we tint them a muted scar-green here so the burnt region reads contiguous.
    # They stay visibly green (not charred) — we are not claiming they burned.
    def _is_dark(cc):
        return cc.is_burnt() or getattr(cc, "has_burned", False)
    for (x, y), c in fire_cells.items():
        if "%d,%d" % (x, y) in cells:
            continue  # already fire/smoke/charred
        if c.smoke.is_smoke_active() or c.is_burning() or _is_dark(c):
            continue
        dark_n = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = fire_cells.get((x + dx, y + dy))
            if n is not None and _is_dark(n):
                dark_n += 1
        if dark_n >= 2:
            cells["%d,%d" % (x, y)] = "#2f4a1a"  # muted "spared vegetation" green

    uavs = [{"id": str(getattr(a, "unique_id", "")), "x": int(a.pos[0]), "y": int(a.pos[1]),
             "color": _role_color(getattr(a, "current_role", ""))}
            for a in model.schedule.agents if type(a).__name__ == "UAV"]
    vics = [{"id": str(getattr(a, "unique_id", "")), "x": int(a.pos[0]), "y": int(a.pos[1]),
             "color": _victim_color(getattr(a, "status", "candidate"))}
            for a in model.schedule.agents if type(a).__name__ == "Victim"]
    ffs = []
    assignments = []  # firefighter -> assigned-victim lines (A)
    for a in model.schedule.agents:
        if type(a).__name__ == "Firefighter":
            fx, fy = int(a.pos[0]), int(a.pos[1])
            dead = str(getattr(a, "status", "") or "").strip().lower() == "dead"
            ffs.append({"id": str(getattr(a, "unique_id", "")), "x": fx, "y": fy,
                        "color": "#000000" if dead else "#00FFCC"})
            # draw a line to its target (the assigned victim's cell) while actively assigned
            tgt = getattr(a, "target_pos", None)
            if (not dead) and getattr(a, "assigned", False) and tgt and not getattr(a, "exiting", False):
                assignments.append({"fx": fx, "fy": fy, "tx": int(tgt[0]), "ty": int(tgt[1])})

    # Walked trails (B): accumulate each firefighter's and UAV's position history for this
    # session, capped to a recent window so the trail fades rather than clutters.
    trails = SESSION.setdefault("trails", {})
    for a in model.schedule.agents:
        tname = type(a).__name__
        if tname not in ("Firefighter", "UAV"):
            continue
        uid = str(getattr(a, "unique_id", ""))
        key = tname + ":" + uid
        hist = trails.setdefault(key, [])
        pt = [int(a.pos[0]), int(a.pos[1])]
        if not hist or hist[-1] != pt:
            hist.append(pt)
            if len(hist) > 60:
                del hist[0]
    ff_trails = [{"id": k.split(":", 1)[1], "kind": "ff", "pts": v}
                 for k, v in trails.items() if k.startswith("Firefighter:")]
    uav_trails = [{"id": k.split(":", 1)[1], "kind": "uav", "pts": v}
                  for k, v in trails.items() if k.startswith("UAV:")]

    return {"step": step, "cells": cells, "prob": prob,
            "uavs": uavs, "victims": vics, "firefighters": ffs,
            "assignments": assignments, "trails": ff_trails + uav_trails,
            "panel": _slim_panel(st)}


def _resolve_seed(raw_seed) -> int:
    """Use a fixed non-negative integer seed, or pick a fresh random one."""
    if raw_seed is None:
        return random.randrange(1, 2**31 - 1)
    if isinstance(raw_seed, str):
        text = raw_seed.strip()
        if not text or text.lower() == "random":
            return random.randrange(1, 2**31 - 1)
        try:
            value = int(text)
        except ValueError:
            return random.randrange(1, 2**31 - 1)
        if value < 0:
            return random.randrange(1, 2**31 - 1)
        return value
    try:
        value = int(raw_seed)
    except (TypeError, ValueError):
        return random.randrange(1, 2**31 - 1)
    if value < 0:
        return random.randrange(1, 2**31 - 1)
    return value


def _build_evaluation(model, terminal_step, steps, params):
    mv = getattr(model, "managed_victims", {}) or {}
    rescued = dead = unreachable = candidate = 0
    for st in mv.values():
        s = str(getattr(st, "status", "")).lower()
        if s == "rescued":
            rescued += 1
        elif s == "dead":
            dead += 1
        elif s == "unreachable":
            unreachable += 1
        else:
            candidate += 1
    ff_dead = 0
    for ff in (getattr(model, "firefighter_marker_agents", {}) or {}).values():
        if getattr(ff, "dead", False) or str(getattr(ff, "status", "")).lower() == "dead":
            ff_dead += 1
    burnt = sum(1 for c in model.schedule.agents
                if type(c).__name__ == "Fire" and getattr(c, "burnt", False))
    total_v = max(rescued + dead + unreachable + candidate, 1)
    return {"rescued": rescued, "dead": dead, "unreachable": unreachable, "candidate": candidate,
            "total_victims": rescued + dead + unreachable + candidate, "firefighter_deaths": ff_dead,
            "burnt_cells": burnt, "steps_run": steps, "terminal_step": terminal_step,
            "all_terminal": candidate == 0, "rescue_rate": round(100.0 * rescued / total_v, 1),
            "wind": params["WIND_DIRECTION"],
            "scenario": "%dUAV/%dV/%dFF" % (params["NUM_AGENTS"], params["NUM_VICTIMS"], params["NUM_FIREFIGHTERS"])}


def _start(cfg):
    with _lock:
        seed_used = _resolve_seed(cfg.get("seed"))
        rng = random.Random(seed_used)
        cfv.SYSTEM_RANDOM = rng
        wf.SYSTEM_RANDOM = rng
        am.random = rng
        ft_cfg = cfg.get("NUM_FIRE_TRACKERS")
        vs_cfg = cfg.get("NUM_VICTIM_SEARCHERS")
        if ft_cfg is not None or vs_cfg is not None:
            num_fire_trackers = max(0, int(ft_cfg or 0))
            num_victim_searchers = max(0, int(vs_cfg or 0))
            num_agents = num_fire_trackers + num_victim_searchers
            if num_agents < 1:
                num_agents = max(1, int(cfg.get("NUM_AGENTS", 1)))
        else:
            num_agents = int(cfg["NUM_AGENTS"])
            num_fire_trackers = None
            num_victim_searchers = None
        params = dict(
            NUM_AGENTS=num_agents,
            NUM_VICTIMS=int(cfg["NUM_VICTIMS"]),
            NUM_FIREFIGHTERS=int(cfg["NUM_FIREFIGHTERS"]),
            WIND_DIRECTION=str(cfg.get("wind", "east")),
            BATCH_SIZE=int(cfg.get("batch_size", 300)),
            FIRE_SPREAD_MULTIPLIER=float(cfg.get("fire_spread", 0.75)),
            PROBABILITY_MAP=False,
        )
        if ft_cfg is not None or vs_cfg is not None:
            params["NUM_FIRE_TRACKERS"] = num_fire_trackers
            params["NUM_VICTIM_SEARCHERS"] = num_victim_searchers
        else:
            params["NUM_FIRE_TRACKERS"] = max(0, num_agents - 1)
            params["NUM_VICTIM_SEARCHERS"] = min(1, num_agents)
        apply_scenario_config(cfv, wf, **params)
        model = WildFireModel()
        model.debug_log = False
        SESSION.update(model=model, step=0, steps=int(cfg.get("steps", 100)),
                       params=params, terminal_step=None, finished=False, trails={},
                       seed_used=seed_used)
        W = getattr(cfv, "WIDTH", 50)
        H = getattr(cfv, "HEIGHT", 50)
        # frame 0 (initial state, before any step)
        frame = _capture_frame(model, 0)
        return {"ok": True, "width": W, "height": H, "params": params,
                "steps": SESSION["steps"], "frame": frame, "seed_used": seed_used}


def _step():
    with _lock:
        model = SESSION.get("model")
        if model is None:
            return {"error": "no active simulation"}
        if SESSION["finished"]:
            return {"frame": _capture_frame(model, SESSION["step"]), "running": False,
                    "finished": True,
                    "evaluation": _build_evaluation(model, SESSION["terminal_step"],
                                                    SESSION["step"], SESSION["params"])}
        model.step()
        SESSION["step"] += 1
        frame = _capture_frame(model, SESSION["step"])
        ms = frame["panel"].get("mission_status", {}) or {}
        if SESSION["terminal_step"] is None and ms.get("all_victims_terminal"):
            SESSION["terminal_step"] = SESSION["step"]
        running = SESSION["step"] < SESSION["steps"]
        if not running:
            SESSION["finished"] = True
        out = {"frame": frame, "running": running, "finished": SESSION["finished"]}
        if SESSION["finished"]:
            out["evaluation"] = _build_evaluation(model, SESSION["terminal_step"],
                                                  SESSION["step"], SESSION["params"])
        return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, HTML, "text/html; charset=utf-8")
        elif u.path == "/scenarios":
            self._send(200, json.dumps(BUILTIN_SCENARIOS))
        elif u.path == "/step":
            self._send(200, json.dumps(_step(), separators=(",", ":")))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/start":
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n) or b"{}")
            try:
                self._send(200, json.dumps(_start(cfg), separators=(",", ":")))
            except Exception as exc:
                self._send(500, json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Wildfire Mission Dashboard</title>
<style>
:root{--bg:#0b0f14;--card:#1a2129;--card2:#232d38;--line:#2f3b47;--text:#d8dee6;--muted:#8a97a5;
--accent:#4aa3ff;--green:#3ecf8e;--amber:#f5a623;--red:#ff5a5a;--purple:#b07cff;--teal:#22c3c3;}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 800px at 50% -10%,#10161e,#05080c);color:var(--text);
font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;padding:16px}
h1{font-size:19px;margin:0;font-weight:700}
.badge{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:600;white-space:nowrap}
.bar-top{max-width:1560px;margin:0 auto 14px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.setup{max-width:1560px;margin:0 auto 14px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap}
.fld{display:flex;flex-direction:column;gap:3px}
.fld label{color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.4px}
select,input{background:var(--card2);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:5px 8px;font-size:12px}
input[type=number]{width:74px}
button{background:var(--accent);color:#06121f;border:none;border-radius:7px;padding:8px 16px;cursor:pointer;font-size:13px;font-weight:700}
button:hover{filter:brightness(1.1)}button:disabled{opacity:.5;cursor:default}
button.ghost{background:var(--card2);color:var(--text);border:1px solid var(--line);font-weight:600}
button.ghost.on{border-color:var(--teal);color:var(--teal)}
.layout{display:grid;grid-template-columns:300px minmax(420px,1fr) 300px;gap:14px;max-width:1560px;margin:0 auto;align-items:start}
.col{display:flex;flex-direction:column;gap:14px}.center{display:flex;flex-direction:column;align-items:center;gap:9px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card.fire{border-left:3px solid var(--red)}.card.comms{border-left:3px solid var(--accent)}
.card.failsafe{border-left:3px solid var(--amber)}.card.victims{border-left:3px solid var(--green)}
.card.ff{border-left:3px solid var(--amber)}.card.alerts{border-left:3px solid var(--red)}
.card.timeline{border-left:3px solid var(--teal)}.card.uavs{border-left:3px solid var(--teal)}
/* timeline moved under the map: square, matches canvas width, scrolls internally */
#timelinecard{width:560px;height:560px;box-sizing:border-box;overflow-y:auto;display:flex;flex-direction:column}
#timelinecard ul{margin:6px 0 0;flex:1}
.card h3{margin:0 0 7px;font-size:12px;text-transform:uppercase;letter-spacing:.5px}
.fire h3{color:var(--red)}.comms h3{color:var(--accent)}.failsafe h3{color:var(--amber)}.victims h3{color:var(--green)}
.ff h3{color:var(--amber)}.alerts h3{color:var(--red)}.timeline h3{color:var(--teal)}.uavs h3{color:var(--teal)}
.kv{display:flex;justify-content:space-between;gap:8px;margin:2px 0}.kv .k{color:var(--muted)}
table{width:100%;border-collapse:collapse}
th{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.4px;padding:3px 5px;border-bottom:1px solid var(--line)}
td{padding:3px 5px;font-size:11.5px;border-bottom:1px solid #2f3b4733}
ul{margin:0;padding:0;list-style:none}li{margin:3px 0;font-size:11.5px;display:flex;gap:6px;align-items:baseline}
canvas{background:#05080c;border:1px solid var(--line);border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,.4)}
.maplabel{color:var(--muted);font-size:12px}
.mission-strip{max-width:1560px;margin:0 auto 14px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.pb{display:flex;height:11px;border-radius:6px;overflow:hidden;background:var(--card2);margin:6px 0}
.legend{display:flex;gap:13px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-top:6px}
.legend span{display:flex;align-items:center;gap:5px}.sw{width:11px;height:11px;border-radius:3px;display:inline-block}
.eval{max-width:1560px;margin:0 auto 14px;background:linear-gradient(180deg,#16202b,#121821);border:1px solid var(--line);
border-left:4px solid var(--green);border-radius:10px;padding:14px 18px;display:none}
.eval h2{margin:0 0 10px;font-size:15px}.eval .grid{display:flex;gap:22px;flex-wrap:wrap}
.eval .stat{display:flex;flex-direction:column;gap:2px}.eval .stat b{font-size:22px}.eval .stat span{color:var(--muted);font-size:11px}
.err{max-width:1560px;margin:0 auto 14px;background:var(--card);border:1px solid var(--red);border-radius:10px;padding:12px;color:var(--red);display:none}
</style></head><body>

<div class="bar-top"><h1>&#x1F6F0; Wildfire Mission Dashboard</h1><span class="maplabel" id="runinfo"></span></div>

<div class="setup">
  <div class="fld"><label>Scenario</label><select id="scenario"><option value="custom">Custom...</option></select></div>
  <div class="fld"><label>UAVs</label><input type="number" id="uavs" value="3" min="1" max="8" readonly title="Fire trackers + victim searchers"></div>
  <div class="fld"><label>Fire trackers</label><input type="number" id="firetrackers" value="2" min="0" max="8"></div>
  <div class="fld"><label>Victim searchers</label><input type="number" id="victimsearchers" value="1" min="0" max="8"></div>
  <div class="fld"><label>Victims</label><input type="number" id="victims" value="5" min="1" max="10"></div>
  <div class="fld"><label>Firefighters</label><input type="number" id="ffs" value="3" min="1" max="8"></div>
  <div class="fld"><label>Wind</label><select id="wind"><option>east</option><option>west</option><option>north</option><option>south</option></select></div>
  <div class="fld"><label>Batch size</label><input type="number" id="batch" value="300" min="10" max="2000" step="10"></div>
  <div class="fld"><label>Steps to run</label><input type="number" id="steps" value="80" min="10" max="600" step="10"></div>
  <div class="fld"><label>Fire spread</label><input type="number" id="spread" value="0.75" min="0.1" max="2" step="0.05"></div>
  <div class="fld"><label>Seed</label><input type="text" id="seed" value="42" placeholder="42 or random" style="width:88px"></div>
  <label class="fld" style="flex-direction:row;align-items:center;gap:6px;padding-bottom:6px;cursor:pointer"><input type="checkbox" id="randseed"> <span style="color:var(--muted);font-size:11px;text-transform:none;letter-spacing:0">Randomize seed</span></label>
  <button id="run">&#9654; Run</button>
  <button class="ghost" id="pause" disabled>&#10074;&#10074; Pause</button>
  <button class="ghost" id="stepbtn" disabled>Step</button>
  <button class="ghost" id="probtoggle">Probability map: off</button>
  <div class="fld"><label>Speed (ms/step)</label><input type="number" id="speed" value="200" min="0" max="2000" step="50"></div>
</div>

<div class="err" id="err"></div>
<div class="eval" id="eval"></div>

<div class="mission-strip" id="strip" style="display:none">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span id="missionmode" class="badge">starting</span>
    <span class="maplabel">step <b id="stepnum" style="color:var(--accent);font-size:15px">0</b> / <span id="maxstep"></span></span>
  </div>
  <div class="pb" id="missionbar"></div>
  <div class="legend">
    <span><i class="sw" style="background:var(--green)"></i>rescued <b id="r">0</b></span>
    <span><i class="sw" style="background:var(--red)"></i>dead <b id="d">0</b></span>
    <span><i class="sw" style="background:var(--amber)"></i>unresolved <b id="u">0</b></span>
    <span style="margin-left:auto">all terminal <b id="terminal">no</b></span>
  </div>
</div>

<div class="layout" id="layout" style="display:none">
  <div class="col">
    <div class="card fire"><h3>Fire</h3><div id="fire"></div></div>
    <div class="card comms"><h3>Comms</h3><div id="comms"></div></div>
    <div class="card failsafe"><h3>Fail-safe</h3><div id="failsafe"></div></div>
  </div>
  <div class="center">
    <canvas id="map" width="560" height="560"></canvas>
    <div class="legend" id="maplegend"></div>
    <div class="card timeline" id="timelinecard"><h3>Timeline</h3><ul id="timeline"></ul></div>
  </div>
  <div class="col">
    <div class="card uavs"><h3>UAVs</h3><div id="uavs_v"></div></div>
    <div class="card victims"><h3>Victims</h3><div id="victims_v"></div></div>
    <div class="card ff"><h3>Firefighters</h3><div id="ff_v"></div></div>
    <div class="card alerts"><h3>Recent Alerts</h3><ul id="alerts"></ul></div>
  </div>
</div>

<script>
const SEV={critical:'var(--red)',warning:'var(--amber)',info:'var(--accent)'};
const STAT={rescued:'var(--green)',available:'var(--green)',dead:'var(--red)',cancelled:'var(--red)',
candidate:'var(--amber)',assigned:'var(--accent)',detected:'var(--accent)',unreachable:'var(--muted)'};
function badge(t,c){return `<span class="badge" style="background:${c}22;color:${c};border:1px solid ${c}55">${t}</span>`;}
function sbadge(s){s=(s||'').toLowerCase();return badge(s||'?',STAT[s]||'var(--muted)');}
function bb(v,tc,fc){return badge(v?'yes':'no',v?(tc||'var(--green)'):(fc||'var(--muted)'));}
function kv(k,v){return `<div class="kv"><span class="k">${k}</span><span>${v}</span></div>`;}
function fmtpos(p){return p&&p.length>=2?`(${Math.round(p[0])}, ${Math.round(p[1])})`:'&mdash;';}
const BW=["#ffffff","#e6e6e6","#c9c9c9","#b1b1b1","#a1a1a1","#818181","#636363","#474747","#303030","#1a1a1a","#000000"];

let W=50,H=50,cs=11.2,probMode=false,playing=false,timer=null,totalSteps=80,curFrame=null,finished=false;
const cv=document.getElementById('map'),ctx=cv.getContext('2d');

fetch('/scenarios').then(r=>r.json()).then(s=>{
  const sel=document.getElementById('scenario');
  for(const k in s){const o=document.createElement('option');o.value=k;o.textContent=s[k].label;sel.appendChild(o);}
  sel.value='A';applyPreset('A',s);sel.onchange=()=>applyPreset(sel.value,s);
});
function syncUavTotal(){
  const ft=Math.max(0,+firetrackers.value||0), vs=Math.max(0,+victimsearchers.value||0);
  uavs.value=Math.max(1,ft+vs);
}
['firetrackers','victimsearchers'].forEach(id=>{
  document.getElementById(id).addEventListener('input',syncUavTotal);
});
function applyPreset(k,s){if(k==='custom')return;
  const n=s[k].NUM_AGENTS||3;firetrackers.value=Math.max(0,n-1);victimsearchers.value=1;syncUavTotal();
  victims.value=s[k].NUM_VICTIMS;ffs.value=s[k].NUM_FIREFIGHTERS;}

document.getElementById('probtoggle').onclick=function(){probMode=!probMode;this.classList.toggle('on',probMode);
  this.textContent='Probability map: '+(probMode?'on':'off');if(curFrame)render(curFrame);};

document.getElementById('randseed').onchange=function(){seed.disabled=this.checked;};
document.getElementById('run').onclick=async function(){
  syncUavTotal();
  const cfg={NUM_AGENTS:+uavs.value,NUM_FIRE_TRACKERS:+firetrackers.value,NUM_VICTIM_SEARCHERS:+victimsearchers.value,
    NUM_VICTIMS:+victims.value,NUM_FIREFIGHTERS:+ffs.value,
    wind:wind.value,batch_size:+batch.value,steps:+steps.value,fire_spread:+spread.value};
  const seedRaw=seed.value.trim();
  const randomize=document.getElementById('randseed').checked;
  if(!randomize && seedRaw!=='' && seedRaw.toLowerCase()!=='random'){
    const fixed=parseInt(seedRaw,10);
    if(!Number.isNaN(fixed)) cfg.seed=fixed;
  }
  document.getElementById('err').style.display='none';
  document.getElementById('eval').style.display='none';
  this.disabled=true;
  let res;
  try{res=await(await fetch('/start',{method:'POST',body:JSON.stringify(cfg)})).json();}
  catch(e){showErr('Could not reach server: '+e);this.disabled=false;return;}
  if(res.error){showErr(res.error);this.disabled=false;return;}
  W=res.width;H=res.height;cs=cv.width/W;totalSteps=res.steps;finished=false;
  document.getElementById('maxstep').textContent=totalSteps;
  document.getElementById('runinfo').textContent=
    res.params.NUM_FIRE_TRACKERS+' FT + '+res.params.NUM_VICTIM_SEARCHERS+' VS ('+res.params.NUM_AGENTS+' UAV) / '
    +res.params.NUM_VICTIMS+' victims / '+res.params.NUM_FIREFIGHTERS+' FF — wind '
    +res.params.WIND_DIRECTION+' — seed '+res.seed_used;
  // show layout immediately with frame 0
  document.getElementById('strip').style.display='block';
  document.getElementById('layout').style.display='grid';
  curFrame=res.frame;render(curFrame);setLegend();
  document.getElementById('pause').disabled=false;document.getElementById('stepbtn').disabled=false;
  startPlaying();
};

function showErr(m){const e=document.getElementById('err');e.style.display='block';e.textContent='Error: '+m;}

async function doStep(){
  if(finished)return;
  let res;
  try{res=await(await fetch('/step')).json();}catch(e){stopPlaying();showErr('step failed: '+e);return;}
  if(res.error){stopPlaying();showErr(res.error);return;}
  curFrame=res.frame;render(curFrame);
  if(!res.running){finished=true;stopPlaying();
    document.getElementById('pause').disabled=true;document.getElementById('stepbtn').disabled=true;
    document.getElementById('run').disabled=false;
    if(res.evaluation)showEval(res.evaluation);}
}
function startPlaying(){playing=true;document.getElementById('pause').innerHTML='&#10074;&#10074; Pause';
  const ms=Math.max(0,+document.getElementById('speed').value||0);
  const loop=async()=>{if(!playing||finished)return;await doStep();if(playing&&!finished)timer=setTimeout(loop,ms);};
  loop();}
function stopPlaying(){playing=false;clearTimeout(timer);document.getElementById('pause').innerHTML='&#9654; Resume';}
document.getElementById('pause').onclick=function(){if(finished)return;if(playing)stopPlaying();else startPlaying();};
document.getElementById('stepbtn').onclick=function(){if(playing)stopPlaying();doStep();};

function setLegend(){document.getElementById('maplegend').innerHTML=probMode
  ?'<span><i class="sw" style="background:#ffffff"></i>low prob</span><span><i class="sw" style="background:#636363"></i>med</span><span><i class="sw" style="background:#000000;border:1px solid #444"></i>high</span><span><i class="sw" style="background:#00FFFF"></i>victim-searcher</span><span><i class="sw" style="background:#FF00FF"></i>fire-tracker</span>'
  :'<span><i class="sw" style="background:#fe5501"></i>fire</span><span><i class="sw" style="background:#ababab"></i>smoke</span><span><i class="sw" style="background:#2b2b2b"></i>charred</span><span><i class="sw" style="background:#2f4a1a"></i>spared veg</span><span><i class="sw" style="background:#FF00FF"></i>fire-tracker</span><span><i class="sw" style="background:#00FFFF"></i>victim-searcher</span><span><i class="sw" style="background:#FFFF00"></i>victim</span><span><i class="sw" style="background:#00FFCC"></i>firefighter</span><span><i class="sw" style="background:#ffd75a"></i>assigned-to</span>';}

function showEval(e){const box=document.getElementById('eval');box.style.display='block';
  const ok=e.all_terminal?'var(--green)':'var(--amber)';box.style.borderLeftColor=ok;
  const tt=e.terminal_step?('all victims terminal at step '+e.terminal_step):(e.all_terminal?'all victims terminal':'ended with unresolved victims');
  box.innerHTML=`<h2>&#x1F3C1; Mission Evaluation <span class="badge" style="background:${ok}22;color:${ok};border:1px solid ${ok}55;margin-left:8px">${e.scenario} · wind ${e.wind}</span></h2>
  <div class="grid"><div class="stat"><b style="color:var(--green)">${e.rescued}</b><span>rescued</span></div>
  <div class="stat"><b style="color:var(--red)">${e.dead}</b><span>dead</span></div>
  <div class="stat"><b style="color:var(--muted)">${e.unreachable}</b><span>unreachable</span></div>
  <div class="stat"><b style="color:var(--amber)">${e.candidate}</b><span>unresolved</span></div>
  <div class="stat"><b style="color:var(--accent)">${e.rescue_rate}%</b><span>rescue rate</span></div>
  <div class="stat"><b style="color:var(--red)">${e.firefighter_deaths}</b><span>FF deaths</span></div>
  <div class="stat"><b style="color:var(--amber)">${e.burnt_cells}</b><span>burnt cells</span></div>
  <div class="stat"><b>${e.steps_run}</b><span>steps run</span></div></div>
  <div class="maplabel" style="margin-top:8px">${tt}</div>`;}

function drawMap(fr){
  if(probMode){ctx.fillStyle='#ffffff';ctx.fillRect(0,0,cv.width,cv.height);
    for(const k in fr.prob){const [x,y]=k.split(',').map(Number);const idx=Math.min(10,Math.max(0,Math.round(fr.prob[k]*10)));
      ctx.fillStyle=BW[idx];ctx.fillRect(x*cs,(H-1-y)*cs,Math.ceil(cs),Math.ceil(cs));}}
  else{ctx.fillStyle='#1c630b';ctx.fillRect(0,0,cv.width,cv.height);
    for(const k in fr.cells){const [x,y]=k.split(',').map(Number);ctx.fillStyle=fr.cells[k];ctx.fillRect(x*cs,(H-1-y)*cs,Math.ceil(cs),Math.ceil(cs));}}
  // cell gridlines: thin lines between every cell so the 50x50 grid is visible
  ctx.strokeStyle='rgba(0,0,0,0.18)';ctx.lineWidth=0.5;ctx.beginPath();
  for(let i=0;i<=W;i++){const gx=Math.round(i*cs)+0.5;ctx.moveTo(gx,0);ctx.lineTo(gx,H*cs);}
  for(let j=0;j<=H;j++){const gy=Math.round(j*cs)+0.5;ctx.moveTo(0,gy);ctx.lineTo(W*cs,gy);}
  ctx.stroke();
  const px=(gx)=>(gx+0.5)*cs, py=(gy)=>(H-1-gy+0.5)*cs;
  // walked trails (B): faint fading polylines of where each unit has been
  for(const t of (fr.trails||[])){const pts=t.pts||[];if(pts.length<2)continue;
    ctx.lineWidth=1.6;ctx.strokeStyle=t.kind==='ff'?'rgba(0,255,204,0.35)':'rgba(120,170,255,0.30)';
    ctx.beginPath();ctx.moveTo(px(pts[0][0]),py(pts[0][1]));
    for(let i=1;i<pts.length;i++)ctx.lineTo(px(pts[i][0]),py(pts[i][1]));ctx.stroke();}
  // assignment lines (A): firefighter -> its assigned victim's cell
  for(const a of (fr.assignments||[])){ctx.lineWidth=1.8;ctx.strokeStyle='rgba(255,215,90,0.8)';
    ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(px(a.fx),py(a.fy));ctx.lineTo(px(a.tx),py(a.ty));ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle='rgba(255,215,90,0.9)';ctx.beginPath();ctx.arc(px(a.tx),py(a.ty),cs*0.28,0,7);ctx.fill();}
  for(const f of fr.firefighters){ctx.fillStyle=f.color;ctx.fillRect((f.x+0.15)*cs,(H-1-f.y+0.15)*cs,cs*0.7,cs*0.7);}
  for(const v of fr.victims){ctx.fillStyle=v.color;ctx.beginPath();ctx.arc((v.x+0.5)*cs,(H-1-v.y+0.5)*cs,cs*0.5,0,7);ctx.fill();}
  for(const u of fr.uavs){ctx.fillStyle=u.color;ctx.fillRect((u.x+0.1)*cs,(H-1-u.y+0.1)*cs,cs*0.8,cs*0.8);
    ctx.strokeStyle='#000';ctx.lineWidth=0.5;ctx.strokeRect((u.x+0.1)*cs,(H-1-u.y+0.1)*cs,cs*0.8,cs*0.8);}
}

function render(fr){
  const p=fr.panel,m=p.mission_status||{},fire=p.fire_view||{},comm=p.communication_view||{},fs=p.fail_safe_view||{};
  document.getElementById('stepnum').textContent=fr.step;
  const rc=m.rescued_count||0,dc=m.dead_victim_count||0,uc=m.unresolved_victim_count||0,tot=Math.max(rc+dc+uc,1);
  r.textContent=rc;d.textContent=dc;u.textContent=uc;
  const mode=m.mission_mode||'?',mc=String(mode).includes('recovery')?'var(--amber)':'var(--green)';
  document.getElementById('missionmode').outerHTML=badge(mode,mc).replace('class="badge"','id="missionmode" class="badge"');
  document.getElementById('terminal').innerHTML=bb(m.all_victims_terminal);
  document.getElementById('missionbar').innerHTML=`<div style="width:${100*rc/tot}%;background:var(--green)"></div><div style="width:${100*dc/tot}%;background:var(--red)"></div><div style="width:${100*uc/tot}%;background:var(--amber)"></div>`;
  const wv=fire.wind_vector||[];
  document.getElementById('fire').innerHTML=kv('active fire',`<b style="color:var(--red)">${fire.active_fire_cells||0}</b>`)+kv('smoke',`<span class="k">${fire.active_smoke_cells||0}</span>`)+kv('burnt',`<b style="color:var(--amber)">${fire.burnt_cells||0}</b>`)+kv('charred',fire.has_burned_cells||0)+kv('wind',`${badge(fire.wind_direction||'?','var(--teal)')} (${wv[0]||0}, ${wv[1]||0})`);
  const conf=comm.delivery_confidence,cc=conf>=0.75?'var(--green)':(conf>=0.5?'var(--amber)':'var(--red)');
  document.getElementById('comms').innerHTML=kv('mode',badge(comm.communication_mode||'?','var(--accent)'))+kv('delivery',`<b style="color:${cc}">${conf!=null?conf.toFixed(2):'&mdash;'}</b>`)+kv('msg load',comm.message_load||0)+kv('relay',bb(comm.relay_needed,'var(--amber)','var(--green)'));
  const fmode=fs.current_mode||'?',fmc=String(fmode).includes('recovery')?'var(--amber)':'var(--green)';
  const trig=[...new Set(fs.active_triggers||[])].slice(0,4).map(t=>badge(t.toLowerCase(),'var(--purple)')).join(' ')||'<span class="k">none</span>';
  document.getElementById('failsafe').innerHTML=kv('mode',badge(fmode,fmc))+kv('critical alerts',`<b style="color:var(--red)">${p.critical_alert_count||0}</b>`)+kv('option cmp',p.option_comparison_count||0)+`<div style="margin-top:5px;display:flex;gap:4px;flex-wrap:wrap">${trig}</div>`;
  let h='<table style="table-layout:fixed;width:100%"><tr><th style="width:16%">uav</th><th style="width:30%">role</th><th style="width:20%">pos</th><th style="width:18%">batt</th></tr>';
  for(const x of (p.uav_status_view||[])){const rcol=String(x.role).includes('tracker')?'var(--teal)':'var(--purple)';const b=x.battery||0,bc=b>=50?'var(--green)':(b>=20?'var(--amber)':'var(--red)');
    h+=`<tr><td><b style="color:var(--accent)">${x.id}</b></td><td>${badge(x.role,rcol)}</td><td>${fmtpos(x.position)}</td><td><b style="color:${bc}">${Math.round(b)}%</b></td></tr>`+
       `<tr><td></td><td colspan="3" class="k" style="word-break:break-word;white-space:normal;padding-top:0;padding-bottom:6px;border-bottom:1px solid var(--line)">${x.execution_action||''}</td></tr>`;}
  document.getElementById('uavs_v').innerHTML=h+'</table>';
  h='<table><tr><th>victim</th><th>pos</th><th>status</th><th>det</th></tr>';
  for(const v of (p.victim_view||[]))h+=`<tr><td><b>${v.id}</b></td><td>${fmtpos(v.position)}</td><td>${sbadge(v.status)}</td><td>${bb(v.detected,'var(--accent)','var(--muted)')}</td></tr>`;
  document.getElementById('victims_v').innerHTML=h+'</table>';
  h='<table><tr><th>unit</th><th>pos</th><th>alive</th><th>blocked</th></tr>';
  for(const f of (p.firefighter_view||[]))h+=`<tr><td><b>${f.id}</b></td><td>${fmtpos(f.position)}</td><td>${f.alive?badge('alive','var(--green)'):badge('dead','var(--red)')}</td><td>${bb(f.route_blocked,'var(--red)','var(--green)')}</td></tr>`;
  document.getElementById('ff_v').innerHTML=h+'</table>';
  let al='';for(const a of (p.alert_list||[]).slice(-5).reverse()){const sev=(a.severity||'info').toLowerCase();al+=`<li>${badge(sev,SEV[sev]||'var(--accent)')}<span class="k">s${a.step}</span><span><b>${a.alert_type}</b> <span class="k">${a.message||''}</span></span></li>`;}
  document.getElementById('alerts').innerHTML=al||'<li class="k">none</li>';
  let tl='';for(const e of (p.timeline||[]).slice(-25).reverse())tl+=`<li><span style="color:var(--accent);font-weight:600">s${e.step}</span><span><b style="color:var(--teal)">${e.event_type}</b> <span class="k">${e.entity_id||''} &middot; ${e.message||''}</span></span></li>`;
  document.getElementById('timeline').innerHTML=tl||'<li class="k">none</li>';
  drawMap(fr);
}
</script></body></html>
"""


def main():
    print("Wildfire live dashboard running.")
    print("Open  http://localhost:%d  in your browser." % PORT)
    print("Press Ctrl+C to stop.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
