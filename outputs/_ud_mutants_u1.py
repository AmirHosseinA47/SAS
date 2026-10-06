"""Urgency round Part 2 - the U1 mutants of 15.3 / 15.4 (outputs/urgency_part1.txt), for the mutation check.

MUTANTS_U1 = {id: (description, [(file, old, new), ...], [pytest node ids])}. Paths are relative to the repo root.
Each mutant is the smallest exact-text change that removes what its tests guard; every `old` matches the CURRENT
source EXACTLY ONCE (newlines written as LF; an applier converts them to the file's own line ending). Every listed
node must FAIL with the mutant applied and PASS on the unmutated source (PYTHONHASHSEED=0). A node naming one
parametrized case must fail itself.

Data only: the applier / runner is the round's outputs/_ud_mutants.py (adapted from the dispatch round's
_dp_mutants.py), which imports this table.
"""

from __future__ import annotations

UD = "src_extension/planning/urgency_dispatch.py"
WM = "wildfire_model.py"
AG = "agents.py"
T = "tests/test_urgency_dispatch.py"


def _t(name: str) -> str:
    return f"{T}::{name}"


TU1 = _t("test_tu1_scarcity_serves_the_smaller_t_even_at_the_higher_index")
TU2B = "test_tu2_in_time_cut_boundary"
TU2M = _t("test_tu2_urgent_but_too_late_is_deferred_and_the_reachable_one_served")
TU3I = "test_tu3_i_reachable_only_through_unclean_cells_is_deferred"
TU3II = "test_tu3_ii_victim_on_an_unclean_cell_is_deferred"
TU3III = _t("test_tu3_iii_a_cell_the_fire_reaches_first_is_refused_and_the_slower_route_used")
TU3IV = "test_tu3_iv_the_units_own_unclean_cell_is_exempt"
TU4Q = "test_tu4_qualifies_table"
TU4M = "test_tu4_not_qualifying_kicks_run_today_verbatim"
TU5 = _t("test_tu5_deferred_is_not_abandoned")
TU6 = _t("test_tu6_flight_changes_t_c_and_the_order_and_a_bound_victim_stays_bound")
TU7C = _t("test_tu7_equal_t_falls_to_the_smaller_c")
TU7I = "test_tu7_then_the_integer_index_victim_10_after_victim_2"
TU8F = _t("test_tu8_t_is_fae_arrival_time_with_the_published_defaults")
TU8N = _t("test_tu8_numpy_bool_burning_is_read_by_truthiness")
TU8K = _t("test_tu8_searcher_fp_knob_moves_the_searcher_estimate_but_not_u1")
TU8S = _t("test_tu8_non_square_grid_indexes_x_by_the_first_extent")
TU9 = _t("test_tu9_the_judged_unit_is_the_unit_sent")
TU10 = _t("test_tu10_all_deferred_keep_todays_index_order")
TU11 = _t("test_tu11_nothing_burns_runs_verbatim")
TCAS = "test_tcas_replacements_still_serve_their_own_victim"
TDRN = _t("test_tdrn_detection_drain_order_is_unchanged")
TFLIP = _t("test_tflip_u_never_unbinds_and_binds_as_many_as_the_index_loop")
TSRC = _t("test_tsrc_u1_code_has_no_path_to_unbind_release_or_write_off")
TINFOA = _t("test_tinfo_a_no_undetected_victim_is_read_by_the_view_or_the_order")
TINFOB = _t("test_tinfo_b_metamorphic_undetected_truth_changes_nothing")
TINFOBR = _t("test_tinfo_b_metamorphic_over_a_short_real_run")
TINFOC = _t("test_tinfo_c_source_reads_only_what_11_1_allows")
TSWON = "test_tsw_on_only_on_an_exact_one"
TSWOFF = "test_tsw_off_for_everything_else"
TSWNE = "test_tsw_off_never_enters_the_urgency_code"
TID = _t("test_tid_off_is_identical_absent_zero_and_base")


def _case(name: str, *ids: str) -> list[str]:
    return [_t(f"{name}[{i}]") for i in ids]


_QUALIFIES = "    return int(n_free) == 1 and int(n_waiting) >= 2 and bool(any_burning)\n"
_PASS_GATE = "        if len(free) == 1 and len(waiting) >= 2:\n"
_KEY = "        key = (0, t_v, c, idx) if promotable else (1, idx)\n"
_CUT = "        promotable = c is not None and (c + 1) <= t_v\n"
_ORDER = "                order = ordered\n"
_BODY = ("            if self._dispatch_firefighter_to_victim(vid, by_id.get(vid), \"initial\") and served is None:\n"
         "                served = vid\n")
_TRIAGE_SET = "                triage = (str(getattr(free[0], \"unit_id\", \"\") or \"\"), ordered, records)\n"
_SERVED = "    served_txt = \"none\" if served is None else served\n"
TU1S = _t("test_tu1_the_triage_line_follows_the_bind_and_names_the_victim_bound")
_SWITCH = ("        if agents.dispatch_urgency():\n"
           "            self._urgency_dispatch_pass(managed, markers)\n"
           "            return\n")
_TAIL = ("        snapshot = self.get_rescue_operational_snapshot()\n"
         "        decision = select_rescue_assignment(snapshot, reason, victim_id=vid or None)\n")
_DRAIN = ("        pending = list(queue)\n"
          "        self._rescue_incident_queue = []\n"
          "        return pending\n")

MUTANTS_U1: dict[str, tuple[str, list[tuple[str, str, str]], list[str]]] = {
    # ------------------------------------------------------------------ T-U1
    "tu1_noorder": (
        "the urgency order is computed and printed but not applied (today's index order kept)",
        [(WM, _ORDER, "                order = list(order)\n")],
        [TU1],
    ),
    "tu13_served_head": (
        "13.3 / R1-1: served= is the order's head, not the victim actually bound",
        [(UD, _SERVED, "    served_txt = ordered[0] if ordered else \"\"\n")],
        [TU1S],
    ),
    "tu13_print_before": (
        "13.3 / R1-1: the [UrgencyTriage] line printed before the binds (served = the order's head)",
        [(WM, _TRIAGE_SET,
          _TRIAGE_SET
          + "                print(urgency_dispatch.triage_line(self.evaluation_timesteps_counter, *triage, ordered[0]))\n"
            "                triage = None\n")],
        [TU1S],
    ),
    # ------------------------------------------------------------------ T-U2
    "tu2_cut": (
        "the in-time cut removed: promotable iff a safe route exists",
        [(UD, _CUT, "        promotable = c is not None\n")],
        _case(TU2B, "c<T<c+1") + [TU2M],
    ),
    "tu2_no_pickup": (
        "the pickup step dropped from the cut (c <= T)",
        [(UD, _CUT, "        promotable = c is not None and c <= t_v\n")],
        _case(TU2B, "c<T<c+1") + [TU2M],
    ),
    "tu2_strict": (
        "the cut made strict (c + 1 < T): the boundary c + 1 = T is deferred",
        [(UD, _CUT, "        promotable = c is not None and (c + 1) < t_v\n")],
        _case(TU2B, "c+1=T"),
    ),
    "tu2_cut_and_static": (
        "both guards of c + 1 = T + 1 removed: the in-time cut AND the route's T* entry test",
        [(UD, _CUT, "        promotable = c is not None\n"),
         (UD, "            if not t_star_of(n) > k:\n                continue\n", "")],
        _case(TU2B, "c+1=T+1", "c<T<c+1") + [TU2M],
    ),
    # ------------------------------------------------------------------ T-U3
    "tu3_burning_only": (
        "unclean = burning only (fire-adjacency and smoke dropped from unclean_cells)",
        [(UD,
          "        out.add(cell)\n"
          "        for ox, oy in SEARCH_ORDER:\n"
          "            n = (cell[0] + ox, cell[1] + oy)\n"
          "            if _in_bounds(n, x_size, y_size):\n"
          "                out.add(n)\n"
          "    for x, y in smoky:\n"
          "        out.add((int(x), int(y)))\n"
          "    return out\n",
          "        out.add(cell)\n"
          "    return out\n")],
        _case(TU3I, "smoky") + _case(TU3II, "smoky", "own_cell_smoky", "own_cell_fire_adjacent"),
    ),
    "tu3_smoke_ignored": (
        "smoke ignored (dropped from unclean_cells)",
        [(UD, "    for x, y in smoky:\n        out.add((int(x), int(y)))\n", "")],
        _case(TU3I, "smoky") + _case(TU3II, "smoky", "own_cell_smoky"),
    ),
    "tu3_victim_exempt": (
        "the victim's cell exempt: waiting victims' cells skip the clean and T* tests, and the final unclean check "
        "is dropped",
        [(UD,
          "    hops = safe_route_hops(unit, x_size, y_size, unclean, lambda c: t_star(t_grid, c, x_size, y_size))\n",
          "    _vcells = {(int(cell[0]), int(cell[1])) for _vid, cell in waiting}\n"
          "    hops = safe_route_hops(unit, x_size, y_size, unclean - _vcells,\n"
          "                           lambda c: math.inf if c in _vcells else t_star(t_grid, c, x_size, y_size))\n"),
         (UD, "        if vc in unclean:\n            c = None\n", "")],
        _case(TU3II, "smoky", "fire_adjacent", "own_cell_smoky", "own_cell_fire_adjacent"),
    ),
    "tu3_static_route": (
        "static clean route: the time-expanded T* test removed from the BFS",
        [(UD, "            if not t_star_of(n) > k:\n                continue\n", "")],
        [TU3III],
    ),
    "tu3_unit_not_exempt": (
        "the unit's own unclean cell is not exempt (the BFS does not start from it)",
        [(UD, "    queue = deque([source])\n", "    queue = deque([source] if source not in unclean else [])\n")],
        _case(TU3IV, "smoky", "fire_adjacent"),
    ),
    "tu3_fire_blind_route": (
        "the route ignores the fire: the BFS drops both the unclean test and the T* test",
        [(UD,
          "            if n in hops or not _in_bounds(n, x_size, y_size) or n in unclean:\n"
          "                continue\n"
          "            if not t_star_of(n) > k:\n"
          "                continue\n",
          "            if n in hops or not _in_bounds(n, x_size, y_size):\n"
          "                continue\n")],
        _case(TU3I, "burning", "fire_adjacent", "smoky"),
    ),
    # ------------------------------------------------------------------ T-U4 / T-U11
    "tu4_nfree": (
        "|F| = 1 relaxed to |F| >= 1 (in qualifies and in the pass's pre-check)",
        [(UD, _QUALIFIES, _QUALIFIES.replace("int(n_free) == 1", "int(n_free) >= 1")),
         (WM, _PASS_GATE, _PASS_GATE.replace("len(free) == 1", "len(free) >= 1"))],
        _case(TU4Q, "W2F2fire", "W3F2fire") + _case(TU4M, "F2_W2", "F2_W3"),
    ),
    "tu4_nwait": (
        "|W| >= 2 relaxed to |W| >= 1 (in qualifies and in the pass's pre-check)",
        [(UD, _QUALIFIES, _QUALIFIES.replace("int(n_waiting) >= 2", "int(n_waiting) >= 1")),
         (WM, _PASS_GATE, _PASS_GATE.replace("len(waiting) >= 2", "len(waiting) >= 1"))],
        _case(TU4Q, "W1F1fire") + _case(TU4M, "F1_W1"),
    ),
    "tu4_w_gt_f": (
        "15.3's T-U4 mutant: the |F| = 1 gate replaced by |W| > |F| >= 1 (in qualifies and in the pass's pre-check)",
        [(UD, _QUALIFIES, "    return int(n_waiting) > int(n_free) >= 1 and bool(any_burning)\n"),
         (WM, _PASS_GATE, "        if len(waiting) > len(free) >= 1:\n")],
        _case(TU4Q, "W3F2fire"),
    ),
    "tu4_gate_removed": (
        "15.3's T-U4 mutant: the gate removed (qualifies always True and no pre-check in the pass)",
        [(UD, _QUALIFIES, "    return True\n"),
         (WM, _PASS_GATE, "        if free and waiting:\n")],
        _case(TU4Q, "W1F1fire", "W0F1fire", "W2F0fire", "W2F2fire", "W3F2fire", "W2F1nofire")
        + _case(TU4M, "F1_W1"),
    ),
    "tu4_qualifies_true": (
        "qualifies always True",
        [(UD, _QUALIFIES, "    return True\n")],
        _case(TU4Q, "W1F1fire", "W0F1fire", "W2F0fire", "W2F2fire", "W3F2fire", "W2F1nofire") + [TU11],
    ),
    "tu4_never": (
        "qualifies always False (U1 never acts)",
        [(UD, _QUALIFIES, "    return False\n")],
        _case(TU4Q, "W2F1fire", "W5F1fire") + [TU1],
    ),
    "tu11_no_burning": (
        "the burning condition removed from qualifies (no fire: T = inf, ordered by c)",
        [(UD, _QUALIFIES, "    return int(n_free) == 1 and int(n_waiting) >= 2\n")],
        _case(TU4Q, "W2F1nofire") + [TU11],
    ),
    # ------------------------------------------------------------------ T-U5
    "tu5_drop_deferred": (
        "deferred victims dropped from the iteration at a qualifying kick",
        [(WM, _ORDER, "                order = [v for v in ordered if records[v][\"promotable\"]]\n")],
        [TU5],
    ),
    "tu5_reason": (
        "the reason changed from \"initial\" in _urgency_dispatch_pass (an empty pool then marks the deferred "
        "victim unreachable)",
        [(WM, _BODY, _BODY.replace("\"initial\"", "\"urgency\""))],
        [TU5, TSRC],
    ),
    # ------------------------------------------------------------------ T-U6
    "tu6_spawn_cell": (
        "the view reads the victim's spawn cell instead of her live cell (T and c cached at the detection cell)",
        [(WM,
          "            pos = getattr(marker, \"pos\", None)\n"
          "            if pos is None:\n"
          "                continue\n"
          "            cells.append((vid, (int(pos[0]), int(pos[1]))))\n",
          "            pos = getattr(marker, \"spawn_cell\", None)\n"
          "            if pos is None:\n"
          "                continue\n"
          "            cells.append((vid, (int(pos[0]), int(pos[1]))))\n")],
        [TU6],
    ),
    "tu6_detection_cell": (
        "15.3's T-U6 mutant: T cached at the detection cell (the view reads her first detection position)",
        [(WM,
          "            pos = getattr(marker, \"pos\", None)\n"
          "            if pos is None:\n"
          "                continue\n"
          "            cells.append((vid, (int(pos[0]), int(pos[1]))))\n",
          "            pos = getattr(marker, \"pos\", None)\n"
          "            _rec = self.victim_runtime_model.victims.get(vid)\n"
          "            if _rec is not None and _rec.detection_history:\n"
          "                pos = _rec.detection_history[0][\"position\"]\n"
          "            if pos is None:\n"
          "                continue\n"
          "            cells.append((vid, (int(pos[0]), int(pos[1]))))\n")],
        [TU6],
    ),
    # ------------------------------------------------------------------ T-U7 / T-U10
    "tu7_no_c": (
        "c dropped from the promotable key",
        [(UD, _KEY, "        key = (0, t_v, idx) if promotable else (1, idx)\n")],
        [TU7C],
    ),
    "tu7_string_ids": (
        "the index compared as the id string (\"victim_10\" before \"victim_2\")",
        [(UD, "        idx = victim_index(vid)\n", "        idx = str(vid)\n")],
        _case(TU7I, "promotable", "deferred"),
    ),
    "tu10_deferred_by_t": (
        "deferred victims keyed by T (sorted toward the front) instead of today's index order",
        [(UD, _KEY, "        key = (0, t_v, c, idx) if promotable else (1, t_v, idx)\n")],
        [TU10],
    ),
    # ------------------------------------------------------------------ T-U8
    "tu8_fp_params": (
        "the estimator's parameters read through front_priority_params() (the SEARCHER_FP_* knobs)",
        [(UD,
          "from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time\n",
          "from src_extension.planning.fire_arrival_estimate import arrival_time, "
          "front_priority_params as FrontPriorityParams\n")],
        [TU8F, TU8K],
    ),
    "tu8_xy_swap": (
        "height and width swapped in the arrival_time call",
        [(UD, "    t_grid = arrival_time(x_size, y_size, burning, wind,",
          "    t_grid = arrival_time(y_size, x_size, burning, wind,")],
        [TU8S],
    ),
    "tu8_numpy_identity": (
        "fire_board_sets reads burning by identity with True (blind to the simulator's numpy.bool_)",
        [(AG, "        if agent.is_burning():\n            burning.add(cell)\n",
          "        if agent.is_burning() is True:\n            burning.add(cell)\n")],
        [TU8N, TU8F],
    ),
    "tu8_view_swap": (
        "the view passes grid.height as x_size and grid.width as y_size",
        [(WM, "            \"x_size\": int(self.grid.width),\n            \"y_size\": int(self.grid.height),\n",
          "            \"x_size\": int(self.grid.height),\n            \"y_size\": int(self.grid.width),\n")],
        [TU8S],
    ),
    # ------------------------------------------------------------------ T-U9
    "tu9_loose_f": (
        "F built with a looser filter (no exiting / rescue_completed test)",
        [(WM, "            if self._firefighter_available_for_dispatch(unit)\n        ]\n",
          "            if not getattr(unit, \"dead\", False)\n"
          "            and str(getattr(unit, \"status\", \"\") or \"\").strip().lower() not in (\"dead\", \"route_blocked\")\n"
          "            and not getattr(unit, \"assigned\", False)\n"
          "            and getattr(unit, \"pos\", None) is not None\n"
          "        ]\n")],
        [TU9],
    ),
    # ------------------------------------------------------------------ T-CAS / T-DRN
    "tcas_tail": (
        "U1's ordering applied at the incident handler's tail for casualty and route_blocked replacements",
        [(WM, _TAIL,
          "        if itype in (\"firefighter_casualty\", \"route_blocked\") and agents.dispatch_urgency():\n"
          "            self._urgency_dispatch_pass(self.managed_victims, self.victim_marker_agents)\n"
          "            return\n" + _TAIL)],
        _case(TCAS, "casualty", "route_blocked"),
    ),
    "tdrn_sort": (
        "the detection drain sorted by urgency (T at the victim's cell, ascending) when U1 is on",
        [(WM, _DRAIN,
          "        pending = list(queue)\n"
          "        self._rescue_incident_queue = []\n"
          "        if agents.dispatch_urgency():\n"
          "            _b, _s = agents.fire_board_sets(self)\n"
          "            _t = urgency_dispatch.arrival_time(\n"
          "                int(self.grid.width), int(self.grid.height), _b,\n"
          "                cfv.wind_vector_from_direction(self.wind.wind_direction), urgency_dispatch.FrontPriorityParams())\n"
          "            _m = self.victim_marker_agents\n"
          "            pending.sort(key=lambda inc: float(_t[tuple(_m[inc[\"victim_id\"]].pos)])\n"
          "                         if inc.get(\"victim_id\") in _m and _m[inc[\"victim_id\"]].pos is not None\n"
          "                         else float(\"inf\"))\n"
          "        return pending\n")],
        [TDRN],
    ),
    # ------------------------------------------------------------------ T-FLIP-U / T-SRC
    "tflip_rerank": (
        "a re-rank in _urgency_dispatch_pass releases a bound unit when the most urgent waiting victim is "
        "promotable (pre-emption)",
        [(WM, _ORDER,
          _ORDER
          + "                for _uid, _u in (getattr(self, \"firefighter_marker_agents\", None) or {}).items():\n"
            "                    if (getattr(_u, \"assigned\", False) and not getattr(_u, \"exiting\", False)\n"
            "                            and getattr(_u, \"rescued_victim\", None) is not None\n"
            "                            and not getattr(_u, \"dead\", False) and records[ordered[0]][\"promotable\"]):\n"
            "                        self.apply_physical_rescue_command(PhysicalRescueCommand(\n"
            "                            action=\"unassign\", victim_id=self._victim_id_from_agent(_u.rescued_victim),\n"
            "                            firefighter_id=str(_uid), reason=\"urgency_rerank\",\n"
            "                            metadata={\"reset_victim_pending\": True}))\n"
            "                        break\n")],
        [TFLIP],
    ),
    "tsrc_unassign": (
        "an unassign command added to _urgency_dispatch_pass",
        [(WM, _BODY,
          _BODY
          + "        if not order and free:\n"
            "            self.apply_physical_rescue_command(PhysicalRescueCommand(\n"
            "                action=\"unassign\", victim_id=\"\", firefighter_id=str(getattr(free[0], \"unit_id\", \"\")),\n"
            "                reason=\"urgency\", metadata={}))\n")],
        [TSRC],
    ),
    # ------------------------------------------------------------------ T-INFO
    "tinfo_read": (
        "the view reads the undetected victims' markers (every non-waiting victim's cell, used as an obstacle)",
        [(WM, "            \"smoky\": smoky,\n",
          "            \"smoky\": smoky | {(int(m.pos[0]), int(m.pos[1])) for v, m in self.victim_marker_agents.items()\n"
          "                               if v not in dict(waiting) and m.pos is not None},\n")],
        [TINFOA, TINFOB, TINFOBR],
    ),
    "tinfo_read_one": (
        "15.3's T-INFO-a mutant: the view reads one undetected marker's cell (a pure read, value unused)",
        [(WM, "        burning, smoky = agents.fire_board_sets(self)\n        cells = []\n",
          "        burning, smoky = agents.fire_board_sets(self)\n"
          "        _peek = next((m.pos for v, m in self.victim_marker_agents.items()\n"
          "                      if not getattr(self.managed_victims.get(v), \"confirmed\", False)), None)\n"
          "        cells = []\n")],
        [TINFOA],
    ),
    "tinfo_snapshot": (
        "the view calls get_rescue_operational_snapshot",
        [(WM, "        burning, smoky = agents.fire_board_sets(self)\n        cells = []\n",
          "        burning, smoky = agents.fire_board_sets(self)\n"
          "        _snapshot = self.get_rescue_operational_snapshot()\n"
          "        cells = []\n")],
        [TINFOA, TINFOC],
    ),
    # ------------------------------------------------------------------ T-SW / T-ID
    "tsw_truthy": (
        "DISPATCH_URGENCY read by truthiness instead of an exact 1",
        [(AG, "    return _exact_integer(getattr(cfv, \"DISPATCH_URGENCY\", 0)) == 1\n",
          "    return bool(getattr(cfv, \"DISPATCH_URGENCY\", 0))\n")],
        _case(TSWOFF, "int2", "float0.5", "str2.0", "str_on") + _case(TSWNE, "2", "on"),
    ),
    "tsw_raw_eq": (
        "a raw `== 1` instead of the exact-integer reading (the strings \"1\" and \" 1 \" stay off)",
        [(AG, "    return _exact_integer(getattr(cfv, \"DISPATCH_URGENCY\", 0)) == 1\n",
          "    return getattr(cfv, \"DISPATCH_URGENCY\", 0) == 1\n")],
        _case(TSWON, "str1", "str1_padded"),
    ),
    "tsw_import_time": (
        "the switch read once at import time instead of at call time",
        [(AG, "def dispatch_urgency() -> bool:\n",
          "_DISPATCH_URGENCY_AT_IMPORT = _exact_integer(getattr(cfv, \"DISPATCH_URGENCY\", 0)) == 1\n\n\n"
          "def dispatch_urgency() -> bool:\n"),
         (AG, "    return _exact_integer(getattr(cfv, \"DISPATCH_URGENCY\", 0)) == 1\n",
          "    return _DISPATCH_URGENCY_AT_IMPORT\n")],
        _case(TSWON, "int1", "True", "float1.0", "str1", "str1_padded")
        + _case(TSWOFF, "int0", "int2", "float0.5", "str2.0", "str_on", "str_empty", "None", "missing"),
    ),
    "tsw_default_on": (
        "a missing DISPATCH_URGENCY read as 1",
        [(AG, "    return _exact_integer(getattr(cfv, \"DISPATCH_URGENCY\", 0)) == 1\n",
          "    return _exact_integer(getattr(cfv, \"DISPATCH_URGENCY\", 1)) == 1\n")],
        _case(TSWOFF, "missing"),
    ),
    "tsw_gate": (
        "the switch gate in _try_dispatch_unresolved_confirmed_victims replaced by True",
        [(WM, _SWITCH, _SWITCH.replace("if agents.dispatch_urgency():", "if True:"))],
        _case(TSWNE, "0", "2", "on", "missing"),
    ),
    "tid_print": (
        "an unconditional [UrgencyTriage] print in the kick, before the switch",
        [(WM, _SWITCH,
          "        print(f\"[UrgencyTriage] step={self.evaluation_timesteps_counter} unit= order=[] served=\")\n"
          + _SWITCH)],
        [TID],
    ),
}
