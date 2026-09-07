"""Import SM_AxisProbe.obj and check resulting bounds (expect 100x200x300, base at Z=0)."""
import unreal

proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
src = proj + "Import/SM_AxisProbe.obj"

if unreal.EditorAssetLibrary.does_asset_exist("/Game/Town/Meshes/SM_AxisProbe"):
    unreal.EditorAssetLibrary.delete_asset("/Game/Town/Meshes/SM_AxisProbe")

task = unreal.AssetImportTask()
task.set_editor_property("filename", src)
task.set_editor_property("destination_path", "/Game/Town/Meshes")
task.set_editor_property("destination_name", "SM_AxisProbe")
task.set_editor_property("automated", True)
task.set_editor_property("save", False)
task.set_editor_property("replace_existing", True)

tools = unreal.AssetToolsHelpers.get_asset_tools()
tools.import_asset_tasks([task])
paths = list(task.get_editor_property("imported_object_paths") or [])
print("imported:", paths)

if paths:
    sm = unreal.load_asset(paths[0])
    bb = sm.get_bounding_box()
    print("bounds min:", bb.min, "max:", bb.max)
    mats = sm.get_editor_property("static_materials")
    print("slots:", [str(m.get_editor_property("material_slot_name")) for m in mats])
    mcp_result = {"imported": paths,
                  "min": [bb.min.x, bb.min.y, bb.min.z],
                  "max": [bb.max.x, bb.max.y, bb.max.z]}
else:
    mcp_result = {"imported": []}
