"""Scale the template floor to cover the town so debug points don't float in air."""
import unreal

TOWN_EXT = 12000.0
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

floor = None
for a in eas.get_all_level_actors():
    label = str(a.get_actor_label()).lower()
    print("actor:", a.get_actor_label(), type(a).__name__)
    if "floor" in label:
        floor = a

if floor:
    # the template floor mesh is 1000x1000x20 (SM_Template_Map_Floor); top at z=0
    sx = (TOWN_EXT * 2 + 2000.0) / 1000.0
    floor.set_actor_scale3d(unreal.Vector(sx, sx, 1.0))
    floor.set_actor_location(unreal.Vector(0, 0, -20.0), False, False)
    print("floor scaled to cover town")
else:
    print("no floor actor found")

# deselect all so the volume's orange brush outline doesn't dominate screenshots
eas.set_selected_level_actors([])
ok = les.save_current_level()
print("saved:", ok)
mcp_result = {"floor": bool(floor), "saved": bool(ok)}
