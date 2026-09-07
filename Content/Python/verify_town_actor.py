"""Verify TownActor-driven generation: instance counts on the TownActor."""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
town = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() == "TownActor")
comps = town.get_components_by_class(unreal.InstancedStaticMeshComponent)
by_mesh, total = {}, 0
for c in comps:
    sm = c.get_editor_property("static_mesh")
    k = sm.get_name() if sm else "None"
    n = c.get_instance_count()
    by_mesh[k] = by_mesh.get(k, 0) + n
    total += n
print("props:", {
    "half": town.get_editor_property("town_half_size"),
    "spline": town.get_editor_property("use_spline_roads"),
    "meshes": town.get_editor_property("render_meshes"),
    "style": str(town.get_editor_property("style").get_name()) if town.get_editor_property("style") else None,
})
print("ISM components:", len(comps), "total:", total)
for k, v in sorted(by_mesh.items()):
    print(f"  {k}: {v}")
mcp_result = {"total": total, "by_mesh": by_mesh}
