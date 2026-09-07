"""Final pass: make the PCG component regenerate on level load and save all."""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

vol = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("PCGVolume", "TownActor"))
pcg = vol.get_editor_property("pcg_component")
pcg.set_editor_property("generation_trigger", unreal.PCGComponentGenerationTrigger.GENERATE_ON_LOAD)
print("generation_trigger -> GenerateOnLoad")

ok_level = les.save_current_level()
ok_graph = unreal.EditorAssetLibrary.save_asset("/Game/Town/PCG_TownGraph")
print("level saved:", ok_level, "graph saved:", ok_graph)

# summary of what's in the level output
out = pcg.get_generated_graph_output()
tags = {}
for td in out.get_editor_property("tagged_data"):
    tg = ",".join(str(t) for t in td.get_editor_property("tags"))
    w = td.get_editor_property("data")
    d = w.get_editor_property("data") if w else None
    try:
        n = unreal.PCGBasePointData.cast(d).get_num_points() if d else 0
    except Exception:
        n = 0
    tags[tg] = tags.get(tg, 0) + n
print("final counts:", tags)
mcp_result = {"level_saved": bool(ok_level), "graph_saved": bool(ok_graph), "counts": tags}
