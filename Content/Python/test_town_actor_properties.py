"""Edit TownActor properties and trigger regeneration.

NOTE: Python's set_editor_property does NOT fire PostEditChangeProperty (only
the C++ Details-panel UI does), so we call RegenerateTown() explicitly here to
push the new values into the graph's parameter nodes and generate. A real
Details-panel edit takes the PostEditChangeProperty->RegenerateTown path
automatically.
mcp_args: {"half_size": float?, "meshes": bool?, "spline": bool?, "style": str?}
"""
import unreal

args = globals().get("mcp_args") or {}
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
town = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() == "TownActor")

if "half_size" in args:
    town.set_editor_property("town_half_size", float(args["half_size"]))
    print("town_half_size ->", args["half_size"])
if "meshes" in args:
    town.set_editor_property("render_meshes", bool(args["meshes"]))
    print("render_meshes ->", args["meshes"])
if "spline" in args:
    town.set_editor_property("use_spline_roads", bool(args["spline"]))
    print("use_spline_roads ->", args["spline"])
if "style" in args:
    s = unreal.EditorAssetLibrary.load_asset(args["style"])
    assert s, f"style asset missing: {args['style']}"
    town.set_editor_property("style", s)
    print("style ->", s.get_name())

print("triggering RegenerateTown() explicitly (set_editor_property does not fire PostEditChangeProperty)")
town.call_method("RegenerateTown")
print("RegenerateTown done")
mcp_result = {"ok": True}
