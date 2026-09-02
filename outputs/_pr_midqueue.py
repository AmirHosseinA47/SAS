"""Defect #5 Part-3 verification: fault injected MID-queue (not on the last
entry), against the patched drain and against a verbatim copy of the pre-patch
drain, so the difference is demonstrated rather than asserted.

Queue shape used:  [PM0, PM1, VICTIM(poisoned), PM2, PM3]
The poison is at index 2 of 5, so there are always two entries behind it.

A. patched drain          -> PM2/PM3 still processed, failure reported
B. patched drain, and the
   failure reporter itself
   raises                 -> outer handler fires; PM2/PM3 preserved in the queue
                             and processed on the next drain
C. pre-patch drain (old)  -> PM2/PM3 silently lost, nothing reported
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

BASE = os.path.dirname(os.path.abspath(__file__))

P = {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
     "WIND_DIRECTION": "east", "BATCH_SIZE": 300,
     "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
     "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 2}


# ---------------------------------------------------------------- pre-patch --
def _old_process_pending_agent_removals(self) -> int:
    """Verbatim copy of the drain at c92e136 (wildfire_model.py:2218-2286)."""
    removed = 0
    recycled = 0
    try:
        pending = list(getattr(self, "_agents_pending_removal", []) or [])
        self._agents_pending_removal = []
        finalized_victim_ids: set[str] = set()
        for agent in pending:
            if type(agent) is am.PathMarker or type(agent).__name__ == "PathMarker":
                try:
                    if getattr(agent, "pos", None) is not None:
                        self.grid.remove_agent(agent)
                except Exception:
                    pass
                try:
                    if agent.unique_id in getattr(self.schedule, "_agents", {}):
                        self.schedule.remove(agent)
                except Exception:
                    pass
                removed += 1
            elif type(agent) is am.Victim or type(agent).__name__ == "Victim":
                vid = self._victim_id_from_agent(agent)
                if vid and vid not in finalized_victim_ids:
                    self._finalize_rescued_victim(vid, agent)
                    finalized_victim_ids.add(vid)
                try:
                    agent.status = "rescued"
                except Exception:
                    pass
                try:
                    if getattr(agent, "pos", None) is not None:
                        self.grid.remove_agent(agent)
                except Exception:
                    pass
                try:
                    self.schedule.remove(agent)
                except Exception:
                    pass
                removed += 1
            elif type(agent) is am.Firefighter or type(agent).__name__ == "Firefighter":
                if getattr(agent, "dead", False):
                    try:
                        if getattr(agent, "pos", None) is not None:
                            self.grid.remove_agent(agent)
                    except Exception:
                        pass
                    try:
                        self.schedule.remove(agent)
                    except Exception:
                        pass
                    removed += 1
                    continue
                rescued_victim = getattr(agent, "rescued_victim", None)
                if rescued_victim is not None:
                    vid = self._victim_id_from_agent(rescued_victim)
                    ff_id = str(getattr(agent, "unit_id", "") or "")
                    if vid and vid not in finalized_victim_ids:
                        self._finalize_rescued_victim(
                            vid, rescued_victim, firefighter_id=ff_id
                        )
                        finalized_victim_ids.add(vid)
                self._recycle_firefighter_after_exit(agent)
                recycled += 1
    except Exception:
        pass
    if recycled > 0:
        self._try_dispatch_unresolved_confirmed_victims()
    return removed


# --------------------------------------------------------------- scaffolding --
def build(seed=101):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **P)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m


def make_markers(m, n, y0=5):
    out = []
    for i in range(n):
        pm = am.PathMarker(m.unique_agents_id, m)
        m.unique_agents_id += 1
        m.grid.place_agent(pm, (2 + i, y0))
        m.schedule.add(pm)
        out.append(pm)
    return out


def state(m, a):
    return {
        "type": type(a).__name__,
        "uid": getattr(a, "unique_id", None),
        "on_grid": getattr(a, "pos", None) is not None,
        "in_schedule": getattr(m.schedule, "_agents", {}).get(
            getattr(a, "unique_id", None)) is a,
    }


def queue_ids(m):
    return [getattr(a, "unique_id", None)
            for a in (getattr(m, "_agents_pending_removal", []) or [])]


_real_final = WildFireModel._finalize_rescued_victim
_real_report = WildFireModel._report_pending_removal_failure


def poison_finalize(raise_it=True):
    def _f(self, victim_id, agent=None, firefighter_id=None):
        if raise_it:
            raise RuntimeError("MIDQUEUE-INJECTED-FAULT")
        return _real_final(self, victim_id, agent, firefighter_id)
    WildFireModel._finalize_rescued_victim = _f


def restore_finalize():
    WildFireModel._finalize_rescued_victim = _real_final


def scenario(name, use_old=False, poison_reporter=False):
    m = build()
    pms = make_markers(m, 4)
    victim = list(m.victim_marker_agents.values())[0]
    pending = [pms[0], pms[1], victim, pms[2], pms[3]]
    m._agents_pending_removal = list(pending)
    poison_index = 2
    poison_finalize(True)

    if poison_reporter:
        def _boom(self, agent, detail):
            raise RuntimeError("REPORTER-ALSO-FAILED")
        WildFireModel._report_pending_removal_failure = _boom
    else:
        WildFireModel._report_pending_removal_failure = _real_report

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        if use_old:
            ret = _old_process_pending_agent_removals(m)
        else:
            ret = m._process_pending_agent_removals()
    out1 = buf.getvalue()

    after = [state(m, a) for a in pending]
    q_after = queue_ids(m)

    # Second drain, with the reporter restored, to show preserved entries
    # actually get processed rather than merely sitting in the list.
    WildFireModel._report_pending_removal_failure = _real_report
    buf2 = _io.StringIO()
    with contextlib.redirect_stdout(buf2):
        if use_old:
            ret2 = _old_process_pending_agent_removals(m)
        else:
            ret2 = m._process_pending_agent_removals()
    out2 = buf2.getvalue()
    after2 = [state(m, a) for a in pending]

    restore_finalize()
    WildFireModel._report_pending_removal_failure = _real_report

    tail = [after[i] for i in range(poison_index + 1, len(pending))]
    tail2 = [after2[i] for i in range(poison_index + 1, len(pending))]
    return {
        "name": name,
        "queue_in": [getattr(a, "unique_id", None) for a in pending],
        "poison_at_index": poison_index,
        "entries_behind_poison": len(pending) - poison_index - 1,
        "returned_drain1": ret,
        "returned_drain2": ret2,
        "state_after_drain1": after,
        "queue_after_drain1": q_after,
        "tail_removed_after_drain1": all(
            (not s["on_grid"]) and (not s["in_schedule"]) for s in tail),
        "tail_removed_after_drain2": all(
            (not s["on_grid"]) and (not s["in_schedule"]) for s in tail2),
        "tail_preserved_in_queue_after_drain1": [
            getattr(pending[i], "unique_id", None) in q_after
            for i in range(poison_index + 1, len(pending))],
        "victim_removed": (not after[poison_index]["on_grid"]
                           and not after[poison_index]["in_schedule"]),
        "failures_last_step": int(
            getattr(m, "pending_removal_failures_last_step", 0) or 0),
        "failures_total": int(getattr(m, "pending_removal_failures_total", 0) or 0),
        "stdout_drain1": out1,
        "stdout_drain2": out2,
        "removal_failure_lines": [l for l in (out1 + out2).splitlines()
                                  if "RemovalFailure" in l],
    }


if __name__ == "__main__":
    results = []
    results.append(scenario("A_patched", use_old=False, poison_reporter=False))
    results.append(scenario("B_patched_reporter_also_raises",
                            use_old=False, poison_reporter=True))
    results.append(scenario("C_prepatch_verbatim", use_old=True))

    for r in results:
        print("=" * 72)
        print(r["name"])
        print("  queue in                     :", r["queue_in"],
              "(poison at index %d, %d entries behind it)"
              % (r["poison_at_index"], r["entries_behind_poison"]))
        print("  drain1 returned              :", r["returned_drain1"])
        print("  entries behind poison removed after drain1:",
              r["tail_removed_after_drain1"])
        print("  entries behind poison preserved in queue  :",
              r["tail_preserved_in_queue_after_drain1"])
        print("  entries behind poison removed after drain2:",
              r["tail_removed_after_drain2"])
        print("  poisoned victim removed      :", r["victim_removed"])
        print("  failures counted             :", r["failures_last_step"],
              "(total %d)" % r["failures_total"])
        print("  RemovalFailure lines printed :", len(r["removal_failure_lines"]))
        for l in r["removal_failure_lines"]:
            print("     |", l)
        print("  queue after drain1           :", r["queue_after_drain1"])
    with open(os.path.join(BASE, "_pr_midqueue.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print("=" * 72)
    print("WROTE outputs/_pr_midqueue.json")
