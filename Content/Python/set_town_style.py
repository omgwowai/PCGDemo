"""Re-skin the town: rebuild every StaticMeshSpawner's weighted entries from
Plans/town_styles.json.
mcp_args: {"style": "prototype"}  (a key of styles{}; omit to use active_style;
          also persists the choice back into the json as active_style)
"""
import unreal, json, os

args = globals().get("mcp_args") or {}
GRAPH_PATH = "/Game/Town/PCG_TownGraph"

proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
styles_path = os.path.join(proj, "Plans", "town_styles.json")
with open(styles_path, "r", encoding="utf-8") as f:
    registry = json.load(f)
style_name = args.get("style") or registry["active_style"]
assert style_name in registry["styles"], \
    f"unknown style '{style_name}'; available: {list(registry['styles'])}"
STYLE = registry["styles"][style_name]["categories"]

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"

updated = []
for n in graph.nodes:
    s = n.get_settings()
    if not isinstance(s, unreal.PCGStaticMeshSpawnerSettings):
        continue
    title = str(n.node_title)          # "Spawn <Category>"
    category = title.replace("Spawn ", "").strip()
    if category not in STYLE:
        print(f"skip spawner '{title}': no category '{category}' in style")
        continue
    sel = s.get_editor_property("mesh_selector_instance")
    entries = []
    for e in STYLE[category]:
        m = unreal.EditorAssetLibrary.load_asset(e["mesh"])
        assert m, f"style mesh missing: {e['mesh']}"
        we = unreal.PCGMeshSelectorWeightedEntry()
        we.set_editor_property("weight", e["weight"])
        d = we.get_editor_property("descriptor")
        d.set_editor_property("static_mesh", m)
        we.set_editor_property("descriptor", d)
        entries.append(we)
    sel.set_editor_property("mesh_entries", entries)
    updated.append(category)
unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print(f"style '{style_name}' applied to {len(updated)} spawners:", sorted(updated))

registry["active_style"] = style_name
with open(styles_path, "w", encoding="utf-8") as f:
    json.dump(registry, f, ensure_ascii=False, indent=2)

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
vols = [a for a in eas.get_all_level_actors() if a.get_class().get_name() == "PCGVolume"]
if vols:
    pcg = vols[0].get_editor_property("pcg_component")
    pcg.cleanup(True)
    pcg.generate(True)
    print("regenerated")
mcp_result = {"style": style_name, "spawners_updated": len(updated)}
