"""Destroy ALL ISM components on the PCG volume (orphans included), then clean
regenerate. Use when concurrent generates have left stale instances behind."""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vol = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("PCGVolume", "TownActor"))
pcg = vol.get_editor_property("pcg_component")
pcg.cleanup(True)

comps = vol.get_components_by_class(unreal.InstancedStaticMeshComponent)
killed = 0
for c in list(comps):
    c.destroy_component(c)
    killed += 1
print("destroyed leftover ISM components:", killed)

pcg.generate(True)
comps2 = vol.get_components_by_class(unreal.InstancedStaticMeshComponent)
total = sum(c.get_instance_count() for c in comps2)
by_mesh = {}
for c in comps2:
    sm = c.get_editor_property("static_mesh")
    k = sm.get_name() if sm else "None"
    by_mesh[k] = by_mesh.get(k, 0) + c.get_instance_count()
print("after regen:", len(comps2), "components,", total, "instances")
for k, v in sorted(by_mesh.items()):
    print(f"  {k}: {v}")
mcp_result = {"killed": killed, "components": len(comps2), "total": total, "by_mesh": by_mesh}
