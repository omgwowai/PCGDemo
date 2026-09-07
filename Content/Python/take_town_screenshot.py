"""Take a high-res screenshot of the current viewport (editor view so PCG debug
visualization is included)."""
import unreal

name = mcp_args.get("name", "town_debug.png") if isinstance(globals().get("mcp_args"), dict) else "town_debug.png"
task = unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, name, force_game_view=False)
print("screenshot task started:", task)
mcp_result = {"file": name}
