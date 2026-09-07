"""Rebuild /Game/Town/PCG_TownGraph in place — richer inZOI-like town, v2.

New in v2 (all still debug-point visualization, no meshes):
  CivicPlot - yellow flat plots claiming whole blocks for public services
  School / Hospital - purple / cyan large civic buildings on those plots
  Houses    - jittered position, random yaw, random gaps (less regular)
  StreetTree - dark green roadside trees, offset from lights
  BusStop   - gray shelters at intersections (thinned)
  Bench     - brown roadside benches (sparse)
  Bin       - pink litter bins (sparse, other side)
Civic plots are subtracted from commercial/house/tree candidates (Difference).
"""
import unreal

TOWN_EXT = 12000.0
BLOCK = 3000.0
ROAD_LINE_STEP = 250.0
CAND_STEP = 750.0
GRAPH_PATH = "/Game/Town/PCG_TownGraph"

def mat(p):
    m = unreal.EditorAssetLibrary.load_asset(p)
    assert m, f"missing material {p}"
    return m

MAT_WHITE  = mat("/PCG/DebugObjects/PCG_DebugWhite")
MAT_ORANGE = mat("/PCG/DebugObjects/PCG_DebugOrange")
MAT_RED    = mat("/PCG/DebugObjects/PCG_DebugRed")
MAT_GREEN  = mat("/PCG/DebugObjects/PCG_DebugGreen")
MAT_BLUE   = mat("/PCG/DebugObjects/PCG_DebugBlue")
MAT_YELLOW = mat("/Game/Town/DebugPalette/MI_Debug_Yellow")
MAT_PURPLE = mat("/Game/Town/DebugPalette/MI_Debug_Purple")
MAT_CYAN   = mat("/Game/Town/DebugPalette/MI_Debug_Cyan")
MAT_BROWN  = mat("/Game/Town/DebugPalette/MI_Debug_Brown")
MAT_DGREEN = mat("/Game/Town/DebugPalette/MI_Debug_DarkGreen")
MAT_GRAY   = mat("/Game/Town/DebugPalette/MI_Debug_Gray")
MAT_PINK   = mat("/Game/Town/DebugPalette/MI_Debug_Pink")

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"

in_node, out_node = graph.get_input_node(), graph.get_output_node()
keep = {in_node.get_full_name(), out_node.get_full_name()}
old = [n for n in graph.nodes if n.get_full_name() not in keep]
for n in old:
    graph.remove_node(n)
print(f"cleared {len(old)} old nodes; remaining {len(graph.nodes)}")
in_node.set_node_position(-2400, -700)
out_node.set_node_position(2200, 300)

V, R = unreal.Vector, unreal.Rotator

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

def tag_out(prev, x, y, tag, material):
    n, s = add(unreal.PCGAddTagSettings, x, y, tags_to_add=tag)
    set_debug(s, material)
    prev.add_edge_to("Out", n, "In")
    n.add_edge_to("Out", out_node, "Out")
    return n

# ================= ROADS (row y=-500) =================
n_grid_ns, _ = add(unreal.PCGCreatePointsGridSettings, -2100, -560,
                   grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                   cell_size=V(BLOCK, ROAD_LINE_STEP, 100.0),
                   coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                   set_points_bounds=False)
n_grid_ew, _ = add(unreal.PCGCreatePointsGridSettings, -2100, -440,
                   grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                   cell_size=V(ROAD_LINE_STEP, BLOCK, 100.0),
                   coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                   set_points_bounds=False)
n_roads, _ = add(unreal.PCGUnionSettings, -1800, -500)
n_grid_ns.add_edge_to("Out", n_roads, "In")
n_grid_ew.add_edge_to("Out", n_roads, "In")
n_road_b, _ = add(unreal.PCGBoundsModifierSettings, -1500, -500,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-140.0, -140.0, -5.0), bounds_max=V(140.0, 140.0, 5.0))
n_roads.add_edge_to("Out", n_road_b, "In")
tag_out(n_road_b, 1800, -500, "Road", MAT_WHITE)

# ================= CIVIC PLOTS (row y=-250) =================
# one point per block center (7x7), pick ~20% blocks for public services
n_blocks, _ = add(unreal.PCGCreatePointsGridSettings, -2100, -280,
                  grid_extents=V(TOWN_EXT - 1500.0, TOWN_EXT - 1500.0, 1.0),
                  cell_size=V(BLOCK, BLOCK, 100.0),
                  coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                  set_points_bounds=False)
n_civ_noise, _ = add(unreal.PCGDensityNoiseSettings, -1800, -280,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_blocks.add_edge_to("Out", n_civ_noise, "In")
n_civ_pick, _ = add(unreal.PCGDensityFilterSettings, -1500, -280,
                    lower_bound=0.8, upper_bound=1.0)
n_civ_noise.add_edge_to("Out", n_civ_pick, "In")
# whole-block plot (yellow flat plate)
n_plot_b, _ = add(unreal.PCGBoundsModifierSettings, -1200, -280,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-1300.0, -1300.0, -2.0), bounds_max=V(1300.0, 1300.0, 25.0))
n_civ_pick.add_edge_to("Out", n_plot_b, "In")
tag_out(n_plot_b, 1800, -280, "CivicPlot", MAT_YELLOW)

# split civic buildings into School / Hospital by a second noise
# (distinct seed: with the default seed this node would reproduce the exact
# noise values of n_civ_noise on the same points, sending everything to one side)
n_civ_split, _ = add(unreal.PCGDensityNoiseSettings, -900, -160,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0,
                     seed=1337)
n_civ_pick.add_edge_to("Out", n_civ_split, "In")

n_school_f, _ = add(unreal.PCGDensityFilterSettings, -600, -220, lower_bound=0.0, upper_bound=0.5)
n_civ_split.add_edge_to("Out", n_school_f, "In")
n_school_b, _ = add(unreal.PCGBoundsModifierSettings, -300, -220,
                    mode=unreal.PCGBoundsModifierMode.SET,
                    bounds_min=V(-800.0, -500.0, 0.0), bounds_max=V(800.0, 500.0, 450.0))
n_school_f.add_edge_to("Out", n_school_b, "In")
n_school_x, _ = add(unreal.PCGTransformPointsSettings, 0, -220,
                    rotation_min=R(0.0, 0.0, -90.0), rotation_max=R(0.0, 0.0, 90.0),
                    uniform_scale=False,
                    scale_min=V(0.85, 0.85, 0.9), scale_max=V(1.1, 1.1, 1.2))
n_school_b.add_edge_to("Out", n_school_x, "In")
tag_out(n_school_x, 1800, -220, "School", MAT_PURPLE)

n_hosp_f, _ = add(unreal.PCGDensityFilterSettings, -600, -100, lower_bound=0.5, upper_bound=1.0)
n_civ_split.add_edge_to("Out", n_hosp_f, "In")
n_hosp_b, _ = add(unreal.PCGBoundsModifierSettings, -300, -100,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-650.0, -650.0, 0.0), bounds_max=V(650.0, 650.0, 900.0))
n_hosp_f.add_edge_to("Out", n_hosp_b, "In")
n_hosp_x, _ = add(unreal.PCGTransformPointsSettings, 0, -100,
                  uniform_scale=False,
                  scale_min=V(0.8, 0.8, 0.8), scale_max=V(1.05, 1.05, 1.3))
n_hosp_b.add_edge_to("Out", n_hosp_x, "In")
tag_out(n_hosp_x, 1800, -100, "Hospital", MAT_CYAN)

# ================= BUILDING CANDIDATES minus civic (row y=150) =================
n_cand, _ = add(unreal.PCGCreatePointsGridSettings, -2100, 100,
                grid_extents=V(TOWN_EXT - 400.0, TOWN_EXT - 400.0, 1.0),
                cell_size=V(CAND_STEP, CAND_STEP, 100.0),
                coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                set_points_bounds=False)
n_cand_diff, _ = add(unreal.PCGDifferenceSettings, -1800, 100,
                     density_function=unreal.PCGDifferenceDensityFunction.BINARY)
n_cand.add_edge_to("Out", n_cand_diff, "Source")
n_plot_b.add_edge_to("Out", n_cand_diff, "Differences")

n_dist_road, _ = add(unreal.PCGDistanceSettings, -1500, 100,
                     set_density=True, output_to_attribute=False,
                     maximum_distance=1500.0,
                     source_shape=unreal.PCGDistanceShape.CENTER,
                     target_shape=unreal.PCGDistanceShape.CENTER)
n_cand_diff.add_edge_to("Out", n_dist_road, "Source")
n_roads.add_edge_to("Out", n_dist_road, "Target")

n_band, _ = add(unreal.PCGDensityFilterSettings, -1200, 40, lower_bound=0.15, upper_bound=0.35)
n_dist_road.add_edge_to("Out", n_band, "In")
n_interior, _ = add(unreal.PCGDensityFilterSettings, -1200, 460, lower_bound=0.5, upper_bound=1.0)
n_dist_road.add_edge_to("Out", n_interior, "In")

# district split by distance to town center
n_center, s_center = add(unreal.PCGCreatePointsSettings, -1500, -20,
                         coordinate_space=unreal.PCGCoordinateSpace.WORLD)
s_center.set_editor_property("points_to_create", [unreal.PCGPoint()])
n_dist_c, _ = add(unreal.PCGDistanceSettings, -900, 40,
                  set_density=True, output_to_attribute=False,
                  maximum_distance=TOWN_EXT,
                  source_shape=unreal.PCGDistanceShape.CENTER,
                  target_shape=unreal.PCGDistanceShape.CENTER)
n_band.add_edge_to("Out", n_dist_c, "Source")
n_center.add_edge_to("Out", n_dist_c, "Target")

# ================= COMMERCIAL (row y=150) =================
n_com_f, _ = add(unreal.PCGDensityFilterSettings, -600, 100, lower_bound=0.0, upper_bound=0.42)
n_dist_c.add_edge_to("Out", n_com_f, "In")
n_com_b, _ = add(unreal.PCGBoundsModifierSettings, -300, 150,
                 mode=unreal.PCGBoundsModifierMode.SET,
                 bounds_min=V(-175.0, -175.0, 0.0), bounds_max=V(175.0, 175.0, 500.0))
n_com_f.add_edge_to("Out", n_com_b, "In")
n_com_x, _ = add(unreal.PCGTransformPointsSettings, 0, 150,
                 offset_min=V(-60.0, -60.0, 0.0), offset_max=V(60.0, 60.0, 0.0),
                 rotation_min=R(0.0, 0.0, -6.0), rotation_max=R(0.0, 0.0, 6.0),
                 uniform_scale=False,
                 scale_min=V(0.85, 0.85, 3.0), scale_max=V(1.2, 1.2, 9.5))
n_com_b.add_edge_to("Out", n_com_x, "In")
tag_out(n_com_x, 1800, 150, "Commercial", MAT_ORANGE)

# ================= HOUSES with randomness (row y=300) =================
n_res_f, _ = add(unreal.PCGDensityFilterSettings, -600, 280, lower_bound=0.42, upper_bound=1.0)
n_dist_c.add_edge_to("Out", n_res_f, "In")
# random gaps: drop ~30% of house lots
n_res_noise, _ = add(unreal.PCGDensityNoiseSettings, -450, 340,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_res_f.add_edge_to("Out", n_res_noise, "In")
n_res_thin, _ = add(unreal.PCGDensityFilterSettings, -300, 280, lower_bound=0.3, upper_bound=1.0)
n_res_noise.add_edge_to("Out", n_res_thin, "In")
n_res_b, _ = add(unreal.PCGBoundsModifierSettings, -150, 340,
                 mode=unreal.PCGBoundsModifierMode.SET,
                 bounds_min=V(-150.0, -150.0, 0.0), bounds_max=V(150.0, 150.0, 250.0))
n_res_thin.add_edge_to("Out", n_res_b, "In")
n_res_x, _ = add(unreal.PCGTransformPointsSettings, 100, 280,
                 offset_min=V(-130.0, -130.0, 0.0), offset_max=V(130.0, 130.0, 0.0),
                 rotation_min=R(0.0, 0.0, -14.0), rotation_max=R(0.0, 0.0, 14.0),
                 uniform_scale=False,
                 scale_min=V(0.7, 0.7, 0.8), scale_max=V(1.35, 1.35, 1.9))
n_res_b.add_edge_to("Out", n_res_x, "In")
tag_out(n_res_x, 1800, 280, "House", MAT_RED)

# ================= PARK TREES (row y=450) =================
n_tree_noise, _ = add(unreal.PCGDensityNoiseSettings, -900, 460,
                      mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_interior.add_edge_to("Out", n_tree_noise, "In")
n_tree_f, _ = add(unreal.PCGDensityFilterSettings, -600, 460, lower_bound=0.55, upper_bound=1.0)
n_tree_noise.add_edge_to("Out", n_tree_f, "In")
n_tree_b, _ = add(unreal.PCGBoundsModifierSettings, -300, 460,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-50.0, -50.0, 0.0), bounds_max=V(50.0, 50.0, 300.0))
n_tree_f.add_edge_to("Out", n_tree_b, "In")
n_tree_x, _ = add(unreal.PCGTransformPointsSettings, 0, 460,
                  offset_min=V(-250.0, -250.0, 0.0), offset_max=V(250.0, 250.0, 0.0),
                  uniform_scale=True,
                  scale_min=V(0.6, 0.6, 0.6), scale_max=V(1.5, 1.5, 1.5))
n_tree_b.add_edge_to("Out", n_tree_x, "In")
tag_out(n_tree_x, 1800, 460, "Tree", MAT_GREEN)

# ================= ROADSIDE helper =================
def roadside(y, along_step, side_offset, phase, thin_keep, bmin, bmax, tag, material,
             scale_rng=None, yaw_rng=None):
    """Two line grids (NS/EW roads) -> side offset with phase along road ->
    union -> optional thinning -> bounds -> tag."""
    g_ns, _ = add(unreal.PCGCreatePointsGridSettings, -2100, y - 60,
                  grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                  cell_size=V(BLOCK, along_step, 100.0),
                  coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                  set_points_bounds=False)
    g_ew, _ = add(unreal.PCGCreatePointsGridSettings, -2100, y + 60,
                  grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
                  cell_size=V(along_step, BLOCK, 100.0),
                  coordinate_space=unreal.PCGCoordinateSpace.WORLD,
                  set_points_bounds=False)
    o_ns, _ = add(unreal.PCGTransformPointsSettings, -1800, y - 60,
                  offset_min=V(side_offset, phase, 0.0), offset_max=V(side_offset, phase, 0.0),
                  absolute_offset=True)
    o_ew, _ = add(unreal.PCGTransformPointsSettings, -1800, y + 60,
                  offset_min=V(phase, side_offset, 0.0), offset_max=V(phase, side_offset, 0.0),
                  absolute_offset=True)
    g_ns.add_edge_to("Out", o_ns, "In")
    g_ew.add_edge_to("Out", o_ew, "In")
    u, _ = add(unreal.PCGUnionSettings, -1500, y)
    o_ns.add_edge_to("Out", u, "In")
    o_ew.add_edge_to("Out", u, "In")
    prev = u
    if thin_keep < 1.0:
        nn, _ = add(unreal.PCGDensityNoiseSettings, -1200, y,
                    mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
        prev.add_edge_to("Out", nn, "In")
        nf, _ = add(unreal.PCGDensityFilterSettings, -900, y,
                    lower_bound=1.0 - thin_keep, upper_bound=1.0)
        nn.add_edge_to("Out", nf, "In")
        prev = nf
    b, _ = add(unreal.PCGBoundsModifierSettings, -600, y,
               mode=unreal.PCGBoundsModifierMode.SET, bounds_min=bmin, bounds_max=bmax)
    prev.add_edge_to("Out", b, "In")
    prev = b
    if scale_rng or yaw_rng:
        kw = {}
        if scale_rng:
            kw.update(uniform_scale=True,
                      scale_min=V(scale_rng[0], scale_rng[0], scale_rng[0]),
                      scale_max=V(scale_rng[1], scale_rng[1], scale_rng[1]))
        if yaw_rng:
            kw.update(rotation_min=R(0.0, 0.0, -yaw_rng), rotation_max=R(0.0, 0.0, yaw_rng))
        x, _ = add(unreal.PCGTransformPointsSettings, -300, y, **kw)
        prev.add_edge_to("Out", x, "In")
        prev = x
    tag_out(prev, 1800, y, tag, material)

# street lights: +150 side, every 1500
roadside(620, 1500.0, 150.0, 0.0, 1.0,
         V(-20.0, -20.0, 0.0), V(20.0, 20.0, 400.0), "Light", MAT_BLUE)
# street trees: -150 side, every 1500, phased +750 to interleave with lights
roadside(800, 1500.0, -150.0, 750.0, 1.0,
         V(-60.0, -60.0, 0.0), V(60.0, 60.0, 350.0), "StreetTree", MAT_DGREEN,
         scale_rng=(0.7, 1.35))
# benches: +190 side, every 3000 along, keep 45%
roadside(980, 3000.0, 190.0, 375.0, 0.45,
         V(-45.0, -18.0, 0.0), V(45.0, 18.0, 45.0), "Bench", MAT_BROWN, yaw_rng=8.0)
# bins: -190 side, every 3000 along, keep 35%, phased differently
roadside(1160, 3000.0, -190.0, -650.0, 0.35,
         V(-16.0, -16.0, 0.0), V(16.0, 16.0, 60.0), "Bin", MAT_PINK)

# ================= BUS STOPS at intersections (row y=1340) =================
n_ix, _ = add(unreal.PCGCreatePointsGridSettings, -2100, 1340,
              grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
              cell_size=V(BLOCK, BLOCK, 100.0),
              coordinate_space=unreal.PCGCoordinateSpace.WORLD,
              set_points_bounds=False)
n_ix_o, _ = add(unreal.PCGTransformPointsSettings, -1800, 1340,
                offset_min=V(280.0, 280.0, 0.0), offset_max=V(280.0, 280.0, 0.0),
                absolute_offset=True)
n_ix.add_edge_to("Out", n_ix_o, "In")
n_bus_noise, _ = add(unreal.PCGDensityNoiseSettings, -1500, 1340,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_ix_o.add_edge_to("Out", n_bus_noise, "In")
n_bus_f, _ = add(unreal.PCGDensityFilterSettings, -1200, 1340, lower_bound=0.55, upper_bound=1.0)
n_bus_noise.add_edge_to("Out", n_bus_f, "In")
n_bus_b, _ = add(unreal.PCGBoundsModifierSettings, -900, 1340,
                 mode=unreal.PCGBoundsModifierMode.SET,
                 bounds_min=V(-140.0, -55.0, 0.0), bounds_max=V(140.0, 55.0, 190.0))
n_bus_f.add_edge_to("Out", n_bus_b, "In")
tag_out(n_bus_b, 1800, 1340, "BusStop", MAT_GRAY)

ok = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("graph saved:", ok, "total nodes:", len(graph.nodes))
mcp_result = {"saved": bool(ok), "node_count": len(graph.nodes)}
