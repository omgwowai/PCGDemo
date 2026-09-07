"""Toggle the town graph's in-graph render mode switch and regenerate.
mcp_args: {"meshes": true|false}  (true = real meshes, false = debug points)
"""
import unreal

args = globals().get("mcp_args") or {}
want_meshes = bool(args.get("meshes", True))
GRAPH_PATH = "/Game/Town/PCG_TownGraph"

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"

switch = None
for n in graph.nodes:
    s = n.get_settings()
    if isinstance(s, unreal.PCGCreateAttributeSetSettings) and "MODE SWITCH" in str(n.node_title):
        switch = (n, s)
        break
assert switch, "MODE SWITCH node not found"
n, s = switch
at = s.get_editor_property("attribute_types")
at.set_editor_property("bool_value", want_meshes)
s.set_editor_property("attribute_types", at)
print("switch set to:", "MESHES" if want_meshes else "DEBUG POINTS")
unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)

# regenerate if the town level is open
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vols = [a for a in eas.get_all_level_actors() if a.get_class().get_name() == "PCGVolume"]
if vols:
    pcg = vols[0].get_editor_property("pcg_component")
    pcg.cleanup(True)
    pcg.generate(True)
    print("regenerated")
else:
    print("no PCGVolume in current level; open Lvl_Town and regenerate")
mcp_result = {"mode": "meshes" if want_meshes else "debug"}
