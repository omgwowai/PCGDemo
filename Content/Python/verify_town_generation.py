"""Verify the town PCG generation: check component state and per-tag point counts."""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vols = [a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("PCGVolume", "TownActor")]
print("volumes:", [str(v.get_actor_label()) for v in vols])
assert vols, "no PCGVolume in level"
vol = vols[0]
pcg = vol.get_editor_property("pcg_component")
print("generated flag:", pcg.get_editor_property("generated"))

out = pcg.get_generated_graph_output()
tagged = out.get_editor_property("tagged_data")
print("tagged_data entries:", len(tagged))

counts = {}
for td in tagged:
    tags = [str(t) for t in td.get_editor_property("tags")]
    wrapper = td.get_editor_property("data")
    data = wrapper.get_editor_property("data") if wrapper else None
    n = -1
    try:
        pdata = unreal.PCGBasePointData.cast(data) if data else None
        if pdata:
            n = pdata.get_num_points()
    except Exception as e:
        print("   cast failed:", type(data).__name__, e)
    key = ",".join(sorted(tags)) or "(untagged)"
    counts[key] = counts.get(key, 0) + max(n, 0)
    print(f"  tags={tags} type={type(data).__name__} points={n}")

mcp_result = {"generated": bool(pcg.get_editor_property("generated")), "counts": counts}
