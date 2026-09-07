# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

UE 5.7 project (`PCG.uproject`, engine at `D:\UE_5.7`) for procedural city/town generation with the engine's PCG framework, driven remotely from Claude Code through an MCP bridge. Nearly all work happens by running Python inside the editor via the `mcp__unreal__run_unreal_script` tool — not by editing C++.

## Critical naming trap: PCG vs PCGGame

The engine plugin "Procedural Content Generation Framework" owns the module name `PCG` / package `/Script/PCG`. The game module was therefore renamed to **PCGGame** (`Source/PCGGame/`, `IMPLEMENT_PRIMARY_GAME_MODULE(... PCGGame ...)`, log category `LogPCGGame`).

- New game code goes in `Source/PCGGame/` with `PCGGAME_API`.
- `Config/DefaultEngine.ini` carries per-class `+ActiveClassRedirects` from `/Script/PCG.X` to `/Script/PCGGame.X`. Never replace them with a package-level redirect — it would hijack the engine plugin's classes.
- If `Binaries/Win64/UnrealEditor-PCG.dll` ever reappears, delete it; it collides with the engine plugin DLL.

## Build (C++ changes only)

```powershell
& "D:\UE_5.7\Engine\Build\BatchFiles\Build.bat" PCGEditor Win64 Development -Project="E:\PCG\PCG.uproject" -WaitMutex
```

Fails with "Live Coding is active" while the editor runs — close the editor first (`unreal.SystemLibrary.quit_editor()` via MCP; check for dirty packages before quitting). There are no tests or linters; verification is done in-editor (see below).

## Working with the editor via MCP

The `unreal` MCP server (`.mcp.json` → `mcp_server/`, standalone Python venv) forwards to the `UnrealMcpBridge` plugin (WebSocket, 127.0.0.1:8765) and runs scripts from `Content/Python/` in the editor's embedded interpreter. Scripts receive `mcp_args` (global) and return JSON via `mcp_result`.

- **Always follow the `driving-unreal-via-mcp` skill**: introspect the real API first (write a read-only `_explore.py`, read signatures from docstrings), then write the real script. Its `references/gotchas.md` covers threading, transactions, saving, path formats.
- If the tool reports "not connected", the editor isn't running — ask the user to launch it; don't retry.
- If the port listens but calls time out after an editor crash, the editor is stuck on the package-restore modal: kill the process, delete `Saved/Autosaves/PackageRestoreData.json`, relaunch.
- **Never import OBJ via AssetImportTask** — crashes UE 5.7.4 (Interchange TaskGraph assertion). Build meshes with GeometryScript (`unreal.GeometryScript_*` libraries, not `GeometryScriptLibrary_*`).

A longer list of verified PCG-Python pitfalls (selector `import_text`, Union→AttributeNoise `$Density` failure, duplicate-seed noise, delete/recreate asset failures, screenshot throttling, …) lives in `.claude/skills/city-planning/references/pcg-conversion.md` — read it before graph-building work.

## Town generation architecture

**User-facing entry point: `ATownActor`** (`Source/PCGGame/Town/`, subclasses APCGVolume). Place one in a level, assign the town graph, and tune everything from the Details panel: `TownHalfSize`, `bUseSplineRoads`, `bRenderMeshes`, `Style` (a `UTownStyleData` DataAsset mapping category name → weighted static-mesh list). Property edits auto-regenerate via `PostEditChangeProperty`; the actor pushes values into the graph's named parameter nodes and rebuilds spawner entries from the Style asset. When editing PCG settings objects from C++, commit changes with `Modify()` + `PostEditChangeProperty` (called through a `UObject*` cast — UPCGSettings redeclares it protected) or the executor cache silently serves stale results.

The generated town lives in `/Game/Town`:

- **`PCG_TownGraph`** — one PCG graph, ~183 nodes, 12 category branches (Road, CivicPlot, School, Hospital, Commercial, House, Tree, Light, StreetTree, Bench, Bin, BusStop). Every branch follows the same skeleton: point generation → spatial filtering (Distance + DensityFilter) → randomization (DensityNoise/TransformPoints) → AddTags → **Branch node** → Output A = colored debug points, Output B = StaticMeshSpawner with real meshes. Road-relative branches (all roadside furniture) are dual-source: a grid lattice path and a spline-sampled path joined by a BooleanSelect on the road-source switch, so furniture follows whichever road source is active.
- **Named parameter nodes** (`CreateAttributeSet`, found by node title): "MODE SWITCH" (`bOutputToB` → every Branch), "ROAD SOURCE SWITCH" (`bUseInputB` → BooleanSelect between grid roads and spline roads sampled from actors tagged `TownRoad`), "SIZE GridExtents Full/Cand/Block" and "SIZE MaxDistance" (town size). The output attribute name must equal the target node's param pin label — that's how the override binds. Graph user parameters don't work from Python (PropertyBag has no add-property API); this node pattern is the workaround, and ATownActor depends on these exact titles.
- **`Lvl_Town`** — level with a TownActor (GenerateOnLoad) covering the town.
- **`Meshes/`** — 13 GeometryScript-built placeholder meshes (base pivot at Z=0, cm scale, per-part material slots); **`MeshMaterials/`** — `M_TownColor` master + color instances; **`Styles/`** — `DA_TownStyle_*` TownStyleData assets (art styles; swap on the actor to re-skin, generated from `Plans/town_styles.json` by `setup_town_actor.py`).

Key `Content/Python/` scripts (all runnable via MCP): `create_town_pcg_graph_v7.py` (rebuilds the graph in place — the current template for new graphs; spline-aware anti-overlap), `build_town_meshes.py` (GeometryScript mesh recipes), `test_town_actor_properties.py` (`{"meshes": bool, "spline": bool, "half_size": cm, "style": path}` — edits the TownActor and calls `RegenerateTown`; note Python's `set_editor_property` does NOT fire `PostEditChangeProperty`, so this script triggers regeneration explicitly), `regen_town.py` (clean regen + per-tag point counts), `verify_town_instances.py` (ISM instance counts), `capture_town_view.py` (SceneCapture2D screenshots — viewport screenshots silently fail when the editor is background-throttled).

**Verification loop for any generation change** (all three must pass): per-tag point counts > 0 → ISM instance counts match → screenshot read back and visually checked. For placement changes also run `audit_town_overlaps_3d.py` (must report zero conflicts; road tiling, civic-buildings-on-plots and tree-crown overhang are whitelisted by design).

**Anti-overlap pattern (v7)**: keep-out volumes are BoundsModifier-inflated copies of a branch's output ("OBSTACLE ..." titled nodes) subtracted from other branches via Difference(BINARY). Difference also eats source points whose own bounds touch the obstacle — always shrink the source to a ±10 marker before the Difference (see `clear_against()` in `create_town_pcg_graph_v7.py`), or a corridor keep-out will silently wipe entire categories. Same-category spacing: BoundsModifier to real footprint + SelfPruning LARGE_TO_SMALL. Roadside items sharing the 1500-lattice must use distinct phases. **Spline mode (v7 fix)**: road plates are sampled every 250 ALONG the spline, so the nearest plate to a furniture item can be offset longitudinally — each furniture category clears a road obstacle inflated to `plate_half(125) + own_long_half + margin`, and its `side_offset` must EXCEED that obstacle's half-width (otherwise `clear_against`, which shrinks to a center marker, culls the item entirely rather than nudging it). Both grid and spline modes must audit clean before finalizing.

Rebuild graphs **in place** (load asset, remove nodes one by one, re-add): deleting and recreating a same-named asset in one session fails due to lingering in-memory packages.

## City-planning skill

For any new city/town request or layout change, invoke the `city-planning` skill first. It runs a four-phase workflow: AskUserQuestion interview → SVG zoning-map Artifact confirmed by the user → `Plans/city_plan.json` + `city_plan.md` → PCG conversion. Do not skip the confirmation phase and build graphs directly.
