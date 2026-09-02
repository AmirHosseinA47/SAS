# python libraries

import mesa

from Canvas_Grid_Visualization import CanvasGrid
from src_extension.dashboard.live_dashboard_panel import DashboardPanel

# own python modules

import wildfire_model
import agents

from common_fixed_variables import *


# creates agent dictionary for rendering it on Canvas Gird from Mesa framework
def agent_portrayal(agent):
    if type(agent) is agents.Victim:
        color = {
            "candidate": "#FFFF00",
            "confirmed": "#FFA500",
            "assigned": "#00AAFF",
            "rescued": "#00AAFF",
            "dead": "#000000",
        }.get(getattr(agent, "status", "candidate"), "#FFFF00")
        return {
            "Shape": "circle",
            "r": 0.5,
            "Filled": True,
            "Color": color,
            "Layer": 3,
        }

    if type(agent) is agents.Firefighter:
        ff_color = (
            "#000000"
            if str(getattr(agent, "status", "") or "").strip().lower() == "dead"
            else "#00FFCC"
        )
        return {
            "Shape": "rect",
            "w": 0.7,
            "h": 0.7,
            "Filled": True,
            "Color": ff_color,
            "Layer": 3,
        }

    if type(agent) is agents.PathMarker:
        return {
            "Shape": "rect",
            "w": 0.35,
            "h": 0.35,
            "Filled": True,
            "Color": "#00BFFF",
            "Layer": 1,
        }

    portrayal = {"Shape": "rect", "Filled": True, "h": 1, "w": 1, "Layer": 0}
    # showing the probability map
    if PROBABILITY_MAP:
        if type(agent) is agents.Fire:
            idx = int(round(agent.get_prob(), 1) * 10)
            portrayal.update({"Color": BLACK_AND_WHITE_COLORS[idx], "Layer": 0})
    else:
        if type(agent) is agents.Fire:  # showing smoke
            if agent.smoke.is_smoke_active():
                # the two following lines of code could be used to set the normalized index for different smoke colors.
                # only one color is used by default.
                # idx = normalize_fuel_values(agent.smoke.get_dispelling_counter_value(),
                # agent.smoke.get_dispelling_counter_start_value())
                portrayal.update({"Color": SMOKE_COLORS[0], "Layer": 0})
            else:
                if agent.is_burning():  # showing fire
                    idx = normalize_fuel_values(agent.get_fuel(), FUEL_UPPER_LIMIT)
                    portrayal.update({"Color": FIRE_COLORS[idx], "Layer": 0})
                elif agent.is_burnt():  # burnt: fuel spent, cannot re-ignite
                    portrayal.update({"Color": "#2b2b2b", "Layer": 0})
                elif getattr(agent, "has_burned", False):  # scorched: fuel left, re-ignites
                    portrayal.update({"Color": "#895e00", "Layer": 0})
                else:  # showing vegetation
                    idx = normalize_fuel_values(agent.get_fuel(), FUEL_UPPER_LIMIT)
                    portrayal.update({"Color": VEGETATION_COLORS[idx], "Layer": 0})
    if type(agent) is agents.UAV:  # showing UAV (works for both rendering modes)
        role = getattr(agent, "current_role", "")
        if role in ("victim_searcher", "victim_search"):
            color = "#00FFFF"
        elif role == "fire_tracker":
            color = "#FF00FF"
        else:
            role_colors = {
                "relay": "#0066CC",
                "victim_confirmer": "#FF8C00",
                "return_to_base": "#888888",
            }
            color = role_colors.get(role, "Black")
        portrayal.update(
            {
                "Color": color,
                "stroke_color": color,
                "Layer": 1,
                "h": 0.8,
                "w": 0.8,
            }
        )
    return portrayal


# launches the original Mesa ModularServer (grid + stacked dashboard panel)
def launch_mesa():
    print('actions:', N_ACTIONS)
    print('observations:', N_OBSERVATIONS)

    # initialize CanvasGrid
    grid = CanvasGrid(agent_portrayal, WIDTH, HEIGHT, 10 * WIDTH, 10 * HEIGHT)
    dashboard_panel = DashboardPanel()
    # initialize Modular server for mesa Python visualization
    server = mesa.visualization.ModularServer(
        wildfire_model.WildFireModel, [grid, dashboard_panel], "WildFire Model"
    )
    server.port = 8521  # default port, others can be set
    server.launch()


# function that holds the main logic, in which the wildfire simulation and the web page interface are launched
def main():
    # By default, launch the live interactive dashboard (environment centered, panels
    # around it, scenario picker, custom scenarios, probability-map toggle, post-mission
    # evaluation). Pass --mesa to fall back to the original Mesa grid view instead.
    import sys

    if "--mesa" in sys.argv:
        launch_mesa()
        return

    print('actions:', N_ACTIONS)
    print('observations:', N_OBSERVATIONS)
    try:
        import webbrowser
        import serve_dashboard
    except Exception as exc:
        print("Could not start the live dashboard (%s); falling back to Mesa view." % exc)
        launch_mesa()
        return

    url = "http://localhost:%d" % serve_dashboard.PORT
    print("Launching live dashboard. Opening %s in your browser." % url)
    print("(Run 'python main.py --mesa' to use the original Mesa grid view instead.)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    serve_dashboard.main()


if __name__ == "__main__":
    main()
