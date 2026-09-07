"""Resize the town by updating the graph's SIZE param nodes, then regenerate.
mcp_args: {"half_size": 12000.0}  (cm; TOWN_EXT half-extent)
Also rescales the PCGVolume and the template Floor if the town level is open.
"""
import unreal

args = globals().get("mcp_args") or {}
half = float(args.get("half_size", 12000.0))
GRAPH_PATH = "/Game/Town/PCG_TownGraph"

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"

V = unreal.Vector
updates = {
    "SIZE GridExtents Full": V(half, half, 1.0),
    "SIZE GridExtents Cand": V(half - 400.0, half - 400.0, 1.0),
    "SIZE GridExtents Block": V(half - 1500.0, half - 1500.0, 1.0),
}
found = set()
for n in graph.nodes:
    title = str(n.node_title)
    s = n.get_settings()
    if not isinstance(s, unreal.PCGCreateAttributeSetSettings):
        continue
    if title in updates:
        at = s.get_editor_property("attribute_types")
        at.set_editor_property("vector_value", updates[title])
        s.set_editor_property("attribute_types", at)
        found.add(title)
    elif title == "SIZE MaxDistance":
        at = s.get_editor_property("attribute_types")
        at.set_editor_property("double_value", half)
        s.set_editor_property("attribute_types", at)
        found.add(title)
missing = (set(updates) | {"SIZE MaxDistance"}) - found
assert not missing, f"param nodes not found: {missing}"
unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print(f"town half-size -> {half} cm ({half*2/100:.0f} m across)")

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vols = [a for a in eas.get_all_level_actors() if a.get_class().get_name() == "PCGVolume"]
if vols:
    vol = vols[0]
    vol.set_actor_scale3d(V(half * 2 / 200.0, half * 2 / 200.0, 4000.0 / 200.0))
    for a in eas.get_all_level_actors():
        if "floor" in str(a.get_actor_label()).lower():
            sx = (half * 2 + 2000.0) / 1000.0
            a.set_actor_scale3d(V(sx, sx, 1.0))
    pcg = vol.get_editor_property("pcg_component")
    pcg.cleanup(True)
    pcg.generate(True)
    print("volume rescaled + regenerated")
else:
    print("town level not open; size will apply on next load/generate")
mcp_result = {"half_size": half, "updated_nodes": sorted(found)}
