"""Force-regenerate the town PCG component and report per-tag point counts."""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vol = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("PCGVolume", "TownActor"))
pcg = vol.get_editor_property("pcg_component")
pcg.cleanup(True)
pcg.generate(True)

out = pcg.get_generated_graph_output()
counts = {}
for td in out.get_editor_property("tagged_data"):
    tg = ",".join(str(t) for t in td.get_editor_property("tags"))
    w = td.get_editor_property("data")
    d = w.get_editor_property("data") if w else None
    try:
        n = unreal.PCGBasePointData.cast(d).get_num_points() if d else 0
    except Exception:
        n = 0
    counts[tg] = counts.get(tg, 0) + n
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")
mcp_result = {"counts": counts}
