"""Switch the town's road source between the procedural grid and level splines.
mcp_args: {"spline": true|false}
Actors with tag "TownRoad" carrying SplineComponents feed the spline path.
"""
import unreal

args = globals().get("mcp_args") or {}
use_spline = bool(args.get("spline", False))
GRAPH_PATH = "/Game/Town/PCG_TownGraph"

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"
node = next((n for n in graph.nodes
             if isinstance(n.get_settings(), unreal.PCGCreateAttributeSetSettings)
             and "ROAD SOURCE SWITCH" in str(n.node_title)), None)
assert node, "ROAD SOURCE SWITCH node not found"
s = node.get_settings()
at = s.get_editor_property("attribute_types")
at.set_editor_property("bool_value", use_spline)
s.set_editor_property("attribute_types", at)
unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("road source ->", "SPLINE actors (tag TownRoad)" if use_spline else "procedural grid")

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vols = [a for a in eas.get_all_level_actors() if a.get_class().get_name() == "PCGVolume"]
if vols:
    if use_spline:
        n_spline_actors = sum(
            1 for a in eas.get_all_level_actors()
            if a.actor_has_tag("TownRoad") and a.get_components_by_class(unreal.SplineComponent))
        print(f"TownRoad spline actors in level: {n_spline_actors}")
        if n_spline_actors == 0:
            print("WARNING: no TownRoad spline actors; Road branch will be empty. "
                  "Create some with spawn_town_road_splines.py")
    pcg = vols[0].get_editor_property("pcg_component")
    pcg.cleanup(True)
    pcg.generate(True)
    print("regenerated")
mcp_result = {"spline": use_spline}
