"""Migrate Lvl_Town to the Details-panel workflow:
1. Create UTownStyleData assets (DA_TownStyle_Prototype / DA_TownStyle_NorthernVillage)
   from Plans/town_styles.json.
2. Replace the plain PCGVolume with an ATownActor, assign graph + style.
3. Regenerate via the actor's own RegenerateTown().
"""
import unreal, json, os

GRAPH_PATH = "/Game/Town/PCG_TownGraph"
STYLE_DIR = "/Game/Town/Styles"

# ---- 1) style data assets from json ----
proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
with open(os.path.join(proj, "Plans", "town_styles.json"), "r", encoding="utf-8") as f:
    registry = json.load(f)

tools = unreal.AssetToolsHelpers.get_asset_tools()

def style_asset_name(key):
    return "DA_TownStyle_" + "".join(w.capitalize() for w in key.split("_"))

created = {}
for key, style in registry["styles"].items():
    name = style_asset_name(key)
    path = f"{STYLE_DIR}/{name}"
    asset = None
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        asset = unreal.EditorAssetLibrary.load_asset(path)
    else:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.TownStyleData)
        asset = tools.create_asset(name, STYLE_DIR, unreal.TownStyleData, factory)
    assert asset, f"failed to create {path}"
    cats = {}
    for cat, entries in style["categories"].items():
        c = unreal.TownMeshCategory()
        arr = []
        for e in entries:
            te = unreal.TownMeshEntry()
            te.set_editor_property("mesh", unreal.EditorAssetLibrary.load_asset(e["mesh"]))
            te.set_editor_property("weight", e["weight"])
            arr.append(te)
        c.set_editor_property("entries", arr)
        cats[cat] = c
    asset.set_editor_property("categories", cats)
    unreal.EditorAssetLibrary.save_asset(path)
    created[key] = path
    print("style asset:", path, f"({len(cats)} categories)")

# ---- 2) swap PCGVolume -> TownActor ----
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "Lvl_Town" not in str(world.get_path_name()):
    les.load_level("/Game/Town/Lvl_Town")
    print("loaded Lvl_Town")

town = None
for a in eas.get_all_level_actors():
    cn = a.get_class().get_name()
    if cn == "TownActor":
        town = a
    elif cn == "PCGVolume":
        eas.destroy_actor(a)
        print("removed old PCGVolume")

if town is None:
    town = eas.spawn_actor_from_class(unreal.TownActor, unreal.Vector(0, 0, 0))
    town.set_actor_label("TownActor")
    print("spawned TownActor")

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
pcg = town.get_editor_property("pcg_component")
pcg.set_graph(graph)
pcg.set_editor_property("generation_trigger", unreal.PCGComponentGenerationTrigger.GENERATE_ON_LOAD)

active_key = registry["active_style"]
style_asset = unreal.EditorAssetLibrary.load_asset(created[active_key])
town.set_editor_property("style", style_asset)
town.set_editor_property("town_half_size", 12000.0)
town.set_editor_property("use_spline_roads", False)
town.set_editor_property("render_meshes", True)

# ---- 3) regenerate through the actor path ----
town.regenerate_town()
ok = les.save_current_level()
print("level saved:", ok)
mcp_result = {"styles": created, "actor": str(town.get_actor_label()), "saved": bool(ok)}
