"""Create /Game/Town/Lvl_Town from the Template_Default map, place a PCGVolume
covering the town area, assign PCG_TownGraph and trigger generation."""
import unreal

LEVEL_PATH = "/Game/Town/Lvl_Town"
GRAPH_PATH = "/Game/Town/PCG_TownGraph"
TOWN_EXT = 12000.0

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(LEVEL_PATH):
    unreal.EditorAssetLibrary.delete_asset(LEVEL_PATH)
    print("deleted old level")

ok = les.new_level_from_template(LEVEL_PATH, "/Engine/Maps/Templates/Template_Default")
print("new level:", ok)
assert ok, "failed to create level"

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"

# enlarge the template floor so debug points sit above ground visually (optional)
vol = eas.spawn_actor_from_class(unreal.PCGVolume, unreal.Vector(0, 0, 0))
vol.set_actor_label("PCG_TownVolume")
# PCGVolume default brush is 200x200x200; scale to cover town, some vertical room
vol.set_actor_scale3d(unreal.Vector(TOWN_EXT * 2 / 200.0, TOWN_EXT * 2 / 200.0, 4000.0 / 200.0))

pcg = vol.get_editor_property("pcg_component")
pcg.set_graph(graph)
pcg.generate(True)
print("generation triggered")

ok_save = les.save_current_level()
print("level saved:", ok_save)
mcp_result = {"level": LEVEL_PATH, "saved": bool(ok_save)}
