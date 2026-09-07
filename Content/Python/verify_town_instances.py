"""Count spawned ISM components/instances per static mesh on the PCG volume."""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vol = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("TownActor", "PCGVolume"))
comps = vol.get_components_by_class(unreal.InstancedStaticMeshComponent)
by_mesh = {}
total = 0
for c in comps:
    sm = c.get_editor_property("static_mesh")
    key = sm.get_name() if sm else "None"
    n = c.get_instance_count()
    by_mesh[key] = by_mesh.get(key, 0) + n
    total += n
print("ISM components:", len(comps), "total instances:", total)
for k, v in sorted(by_mesh.items()):
    print(f"  {k}: {v}")
mcp_result = {"components": len(comps), "total": total, "by_mesh": by_mesh}
