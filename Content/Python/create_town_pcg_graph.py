"""Create /Game/Town/PCG_TownGraph: an inZOI-like town layout rendered purely
with per-node PCG debug visualization (no meshes spawned).

Branches (all tagged + debug-colored):
  Roads  - white flat plates on a grid of NS/EW lines (block pitch 3000)
  Commercial - orange tall towers near town center, fronting roads
  House  - red low boxes fronting roads, outside the center
  Tree   - green boxes in block interiors (thinned by noise)
  Light  - blue thin poles along road edges
"""
import unreal

TOWN_EXT = 12000.0        # half-extent of the town (world units)
BLOCK = 3000.0            # road pitch
ROAD_LINE_STEP = 250.0    # spacing of points along a road line
CAND_STEP = 750.0         # building-candidate grid step

GRAPH_DIR = "/Game/Town"
GRAPH_NAME = "PCG_TownGraph"
GRAPH_PATH = f"{GRAPH_DIR}/{GRAPH_NAME}"

MAT_WHITE = unreal.EditorAssetLibrary.load_asset("/PCG/DebugObjects/PCG_DebugWhite")
MAT_ORANGE = unreal.EditorAssetLibrary.load_asset("/PCG/DebugObjects/PCG_DebugOrange")
MAT_RED = unreal.EditorAssetLibrary.load_asset("/PCG/DebugObjects/PCG_DebugRed")
MAT_GREEN = unreal.EditorAssetLibrary.load_asset("/PCG/DebugObjects/PCG_DebugGreen")
MAT_BLUE = unreal.EditorAssetLibrary.load_asset("/PCG/DebugObjects/PCG_DebugBlue")
assert all([MAT_WHITE, MAT_ORANGE, MAT_RED, MAT_GREEN, MAT_BLUE]), "debug materials missing"

if unreal.EditorAssetLibrary.does_asset_exist(GRAPH_PATH):
    unreal.EditorAssetLibrary.delete_asset(GRAPH_PATH)
    unreal.SystemLibrary.collect_garbage()
    print("deleted existing graph asset")

tools = unreal.AssetToolsHelpers.get_asset_tools()
graph = tools.create_asset(GRAPH_NAME, GRAPH_DIR, unreal.PCGGraph, unreal.PCGGraphFactory())
if graph is None:
    # a same-named in-memory package can linger after delete; fall back to a fresh name
    name, pkg = tools.create_unique_asset_name(f"{GRAPH_DIR}/{GRAPH_NAME}", "")
    GRAPH_NAME = name.split("/")[-1]
    GRAPH_PATH = f"{GRAPH_DIR}/{GRAPH_NAME}"
    graph = tools.create_asset(GRAPH_NAME, GRAPH_DIR, unreal.PCGGraph, unreal.PCGGraphFactory())
    print("fallback name:", GRAPH_PATH)
assert graph, "failed to create graph asset"
out_node = graph.get_output_node()
out_node.set_node_position(1800, 0)
graph.get_input_node().set_node_position(-2100, -600)

def add(cls, x, y, **props):
    node, settings = graph.add_node_of_type(cls)
    node.set_node_position(x, y)
    for k, v in props.items():
        settings.set_editor_property(k, v)
    return node, settings

def set_debug(settings, material):
    ds = settings.get_editor_property("debug_settings")
    ds.set_editor_property("material_override", material)
    ds.set_editor_property("scale_method", unreal.PCGDebugVisScaleMethod.EXTENTS)
    settings.set_editor_property("debug_settings", ds)
    settings.set_editor_property("debug", True)

V = unreal.Vector

# ---------------- roads ----------------
n_grid_ns, _ = add(unreal.PCGCreatePointsGridSettings, -1800, -300,
                   grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                   cell_size=V(BLOCK, ROAD_LINE_STEP, 100.0),
                   coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                   set_points_bounds=False)
n_grid_ew, _ = add(unreal.PCGCreatePointsGridSettings, -1800, -150,
                   grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                   cell_size=V(ROAD_LINE_STEP, BLOCK, 100.0),
                   coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                   set_points_bounds=False)
n_roads_union, _ = add(unreal.PCGUnionSettings, -1500, -220)
n_grid_ns.add_edge_to("Out", n_roads_union, "In")
n_grid_ew.add_edge_to("Out", n_roads_union, "In")

n_road_bounds, _ = add(unreal.PCGBoundsModifierSettings, -1200, -220,
                       mode=unreal.PCGBoundsModifierMode.SET,
                       bounds_min=V(-140.0, -140.0, -5.0),
                       bounds_max=V(140.0, 140.0, 5.0))
n_roads_union.add_edge_to("Out", n_road_bounds, "In")

n_road_tags, s_road_tags = add(unreal.PCGAddTagSettings, 1400, -220, tags_to_add="Road")
set_debug(s_road_tags, MAT_WHITE)
n_road_bounds.add_edge_to("Out", n_road_tags, "In")
n_road_tags.add_edge_to("Out", out_node, "Out")

# ---------------- building candidates ----------------
n_cand, _ = add(unreal.PCGCreatePointsGridSettings, -1800, 300,
                grid_extents=V(TOWN_EXT - 400.0, TOWN_EXT - 400.0, 1.0),
                cell_size=V(CAND_STEP, CAND_STEP, 100.0),
                coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                set_points_bounds=False)

# density <- normalized distance to nearest road centerline (assumed d/max)
n_dist_road, _ = add(unreal.PCGDistanceSettings, -1500, 300,
                     set_density=True, output_to_attribute=False,
                     maximum_distance=1500.0,
                     source_shape=unreal.PCGDistanceShape.CENTER,
                     target_shape=unreal.PCGDistanceShape.CENTER)
n_cand.add_edge_to("Out", n_dist_road, "Source")
n_roads_union.add_edge_to("Out", n_dist_road, "Target")

# street-front band (grid geometry puts fronts at 375 -> 375/1500 = 0.25)
n_band, _ = add(unreal.PCGDensityFilterSettings, -1200, 200,
                lower_bound=0.15, upper_bound=0.35)
n_dist_road.add_edge_to("Out", n_band, "In")

# block interiors (1125 -> 0.75)
n_interior, _ = add(unreal.PCGDensityFilterSettings, -1200, 500,
                    lower_bound=0.6, upper_bound=1.0)
n_dist_road.add_edge_to("Out", n_interior, "In")

# ---------------- district split (distance to town center) ----------------
n_center, s_center = add(unreal.PCGCreatePointsSettings, -1500, 60,
                         coordinate_space=unreal.PCGCoordinateSpace.WORLD)
s_center.set_editor_property("points_to_create", [unreal.PCGPoint()])

n_dist_center, _ = add(unreal.PCGDistanceSettings, -900, 200,
                       set_density=True, output_to_attribute=False,
                       maximum_distance=TOWN_EXT,
                       source_shape=unreal.PCGDistanceShape.CENTER,
                       target_shape=unreal.PCGDistanceShape.CENTER)
n_band.add_edge_to("Out", n_dist_center, "Source")
n_center.add_edge_to("Out", n_dist_center, "Target")

n_com_filter, _ = add(unreal.PCGDensityFilterSettings, -600, 100,
                      lower_bound=0.0, upper_bound=0.42)
n_res_filter, _ = add(unreal.PCGDensityFilterSettings, -600, 350,
                      lower_bound=0.42, upper_bound=1.0)
n_dist_center.add_edge_to("Out", n_com_filter, "In")
n_dist_center.add_edge_to("Out", n_res_filter, "In")

# ---------------- commercial towers ----------------
n_com_bounds, _ = add(unreal.PCGBoundsModifierSettings, -300, 100,
                      mode=unreal.PCGBoundsModifierMode.SET,
                      bounds_min=V(-175.0, -175.0, 0.0),
                      bounds_max=V(175.0, 175.0, 500.0))
n_com_filter.add_edge_to("Out", n_com_bounds, "In")
n_com_scale, _ = add(unreal.PCGTransformPointsSettings, 0, 100,
                     uniform_scale=False,
                     scale_min=V(0.9, 0.9, 3.5),
                     scale_max=V(1.15, 1.15, 9.0))
n_com_bounds.add_edge_to("Out", n_com_scale, "In")
n_com_tags, s_com_tags = add(unreal.PCGAddTagSettings, 1400, 100, tags_to_add="Commercial")
set_debug(s_com_tags, MAT_ORANGE)
n_com_scale.add_edge_to("Out", n_com_tags, "In")
n_com_tags.add_edge_to("Out", out_node, "Out")

# ---------------- residential houses ----------------
n_res_bounds, _ = add(unreal.PCGBoundsModifierSettings, -300, 350,
                      mode=unreal.PCGBoundsModifierMode.SET,
                      bounds_min=V(-150.0, -150.0, 0.0),
                      bounds_max=V(150.0, 150.0, 250.0))
n_res_filter.add_edge_to("Out", n_res_bounds, "In")
n_res_scale, _ = add(unreal.PCGTransformPointsSettings, 0, 350,
                     uniform_scale=False,
                     scale_min=V(0.8, 0.8, 0.9),
                     scale_max=V(1.2, 1.2, 1.5))
n_res_bounds.add_edge_to("Out", n_res_scale, "In")
n_res_tags, s_res_tags = add(unreal.PCGAddTagSettings, 1400, 350, tags_to_add="House")
set_debug(s_res_tags, MAT_RED)
n_res_scale.add_edge_to("Out", n_res_tags, "In")
n_res_tags.add_edge_to("Out", out_node, "Out")

# ---------------- park trees (block interiors, thinned) ----------------
n_tree_noise, _ = add(unreal.PCGDensityNoiseSettings, -900, 500,
                      mode=unreal.PCGAttributeNoiseMode.SET,
                      noise_min=0.0, noise_max=1.0)
n_interior.add_edge_to("Out", n_tree_noise, "In")
n_tree_filter, _ = add(unreal.PCGDensityFilterSettings, -600, 600,
                       lower_bound=0.55, upper_bound=1.0)
n_tree_noise.add_edge_to("Out", n_tree_filter, "In")
n_tree_bounds, _ = add(unreal.PCGBoundsModifierSettings, -300, 600,
                       mode=unreal.PCGBoundsModifierMode.SET,
                       bounds_min=V(-50.0, -50.0, 0.0),
                       bounds_max=V(50.0, 50.0, 300.0))
n_tree_filter.add_edge_to("Out", n_tree_bounds, "In")
n_tree_scale, _ = add(unreal.PCGTransformPointsSettings, 0, 600,
                      uniform_scale=True,
                      scale_min=V(0.6, 0.6, 0.6),
                      scale_max=V(1.4, 1.4, 1.4))
n_tree_bounds.add_edge_to("Out", n_tree_scale, "In")
n_tree_tags, s_tree_tags = add(unreal.PCGAddTagSettings, 1400, 600, tags_to_add="Tree")
set_debug(s_tree_tags, MAT_GREEN)
n_tree_scale.add_edge_to("Out", n_tree_tags, "In")
n_tree_tags.add_edge_to("Out", out_node, "Out")

# ---------------- street lights ----------------
n_light_ns, _ = add(unreal.PCGCreatePointsGridSettings, -1800, 850,
                    grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                    cell_size=V(BLOCK, 1500.0, 100.0),
                    coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                    set_points_bounds=False)
n_light_ew, _ = add(unreal.PCGCreatePointsGridSettings, -1800, 1000,
                    grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                    cell_size=V(1500.0, BLOCK, 100.0),
                    coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                    set_points_bounds=False)
n_light_ns_off, _ = add(unreal.PCGTransformPointsSettings, -1500, 850,
                        offset_min=V(150.0, 0.0, 0.0), offset_max=V(150.0, 0.0, 0.0),
                        absolute_offset=True)
n_light_ew_off, _ = add(unreal.PCGTransformPointsSettings, -1500, 1000,
                        offset_min=V(0.0, 150.0, 0.0), offset_max=V(0.0, 150.0, 0.0),
                        absolute_offset=True)
n_light_ns.add_edge_to("Out", n_light_ns_off, "In")
n_light_ew.add_edge_to("Out", n_light_ew_off, "In")
n_light_union, _ = add(unreal.PCGUnionSettings, -1200, 900)
n_light_ns_off.add_edge_to("Out", n_light_union, "In")
n_light_ew_off.add_edge_to("Out", n_light_union, "In")
n_light_bounds, _ = add(unreal.PCGBoundsModifierSettings, -900, 900,
                        mode=unreal.PCGBoundsModifierMode.SET,
                        bounds_min=V(-20.0, -20.0, 0.0),
                        bounds_max=V(20.0, 20.0, 400.0))
n_light_union.add_edge_to("Out", n_light_bounds, "In")
n_light_tags, s_light_tags = add(unreal.PCGAddTagSettings, 1400, 900, tags_to_add="Light")
set_debug(s_light_tags, MAT_BLUE)
n_light_bounds.add_edge_to("Out", n_light_tags, "In")
n_light_tags.add_edge_to("Out", out_node, "Out")

ok = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("graph saved:", ok, "nodes:", len(graph.nodes))
mcp_result = {"graph": GRAPH_PATH, "saved": bool(ok), "node_count": len(graph.nodes)}
