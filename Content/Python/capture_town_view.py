"""Capture the town from a given camera pose using SceneCapture2D -> PNG.
Works even when the editor window is background-throttled.
mcp_args: name (str), loc [x,y,z], rot [pitch,yaw,roll], fov (float)"""
import unreal

args = globals().get("mcp_args") or {}
name = args.get("name", "town_capture")
lx, ly, lz = args.get("loc", [-20000.0, -20000.0, 12000.0])
pitch, yaw, roll = args.get("rot", [-22.0, 45.0, 0.0])
fov = float(args.get("fov", 70.0))

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(lx, ly, lz),
                                 unreal.Rotator(roll, pitch, yaw), transient=True)
comp = cap.get_editor_property("capture_component2d")
rt = unreal.RenderingLibrary.create_render_target2d(cap, 1600, 900,
                                                    unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
comp.set_editor_property("texture_target", rt)
comp.set_editor_property("fov_angle", fov)
comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
comp.set_editor_property("capture_every_frame", False)
comp.capture_scene()

out_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + "Screenshots/Capture"
path = f"{out_dir}/{name}.png"
ok = unreal.RenderingLibrary.export_render_target(cap, rt, out_dir, f"{name}.png")
print("exported:", path)

eas.destroy_actor(cap)
mcp_result = {"file": path}
