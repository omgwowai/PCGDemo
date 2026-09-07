"""Create custom-colored debug material instances (parent: /PCG/DebugObjects/PCG_DebugWhite)
under /Game/Town/DebugPalette for richer town categories."""
import unreal

PARENT = unreal.EditorAssetLibrary.load_asset("/PCG/DebugObjects/PCG_DebugWhite")
assert PARENT, "parent debug material missing"
DIR = "/Game/Town/DebugPalette"

COLORS = {
    "MI_Debug_Yellow":  (1.0, 0.85, 0.05),   # public service / civic
    "MI_Debug_Purple":  (0.55, 0.1, 0.8),    # school
    "MI_Debug_Cyan":    (0.05, 0.8, 0.85),   # hospital
    "MI_Debug_Brown":   (0.45, 0.28, 0.12),  # street tree trunks / benches
    "MI_Debug_DarkGreen": (0.02, 0.35, 0.08),# street trees
    "MI_Debug_Gray":    (0.35, 0.35, 0.38),  # bus stops / utility
    "MI_Debug_Pink":    (1.0, 0.45, 0.7),    # plaza / park furniture
}

tools = unreal.AssetToolsHelpers.get_asset_tools()
made = []
for name, (r, g, b) in COLORS.items():
    path = f"{DIR}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        made.append(path)
        print("exists:", path)
        continue
    factory = unreal.MaterialInstanceConstantFactoryNew()
    mi = tools.create_asset(name, DIR, unreal.MaterialInstanceConstant, factory)
    assert mi, f"failed to create {name}"
    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, PARENT)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        mi, "Param", unreal.LinearColor(r, g, b, 1.0))
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_asset(path)
    made.append(path)
    print("created:", path)

mcp_result = {"materials": made}
