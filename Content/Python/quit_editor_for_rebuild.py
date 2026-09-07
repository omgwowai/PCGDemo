import unreal

# No dirty packages were found earlier; safe to close for module rebuild.
print("Quitting editor to allow rebuild of renamed game module...")
unreal.SystemLibrary.quit_editor()
mcp_result = {"status": "quit_requested"}
