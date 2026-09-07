"""Rebuild /Game/Town/PCG_TownGraph in place — v3: real meshes via Static Mesh Spawners.

Every branch keeps its AddTags node (semantics/debuggability) but debug viz is
OFF; a PCGStaticMeshSpawner with a weighted mesh selector renders each category:
  Road       SM_RoadPlate            (dedup at intersections via SelfPruning)
  CivicPlot  SM_PlotPlate
  School     SM_SchoolL
  Hospital   SM_HospitalCross
  Commercial SM_Tower                (z point-scale 0.75-2.25 -> 1500-4500 tall)
  House      SM_HouseGable/SM_HouseFlat (weighted mix + jitter/yaw/gaps)
  Tree       SM_TreeRound/SM_TreeConifer
  Light      SM_LampPost             (arm rotated to face the road per NS/EW)
  StreetTree SM_TreeConifer/SM_TreeRound
  Bench      SM_Bench                (back to the road side, facing road)
  Bin        SM_Bin
  BusStop    SM_BusShelter           (opening toward the intersection)
"""
import unreal

TOWN_EXT = 12000.0
BLOCK = 3000.0
ROAD_LINE_STEP = 250.0
CAND_STEP = 750.0
GRAPH_PATH = "/Game/Town/PCG_TownGraph"
MESH_DIR = "/Game/Town/Meshes"

def mesh(name):
    m = unreal.EditorAssetLibrary.load_asset(f"{MESH_DIR}/{name}")
    assert m, f"missing mesh {name}"
    return m

M_ROAD, M_PLOT = mesh("SM_RoadPlate"), mesh("SM_PlotPlate")
M_TOWER, M_HG, M_HF = mesh("SM_Tower"), mesh("SM_HouseGable"), mesh("SM_HouseFlat")
M_SCHOOL, M_HOSP = mesh("SM_SchoolL"), mesh("SM_HospitalCross")
M_TR, M_TC = mesh("SM_TreeRound"), mesh("SM_TreeConifer")
M_LAMP, M_BENCH, M_BIN, M_BUS = mesh("SM_LampPost"), mesh("SM_Bench"), mesh("SM_Bin"), mesh("SM_BusShelter")

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"
in_node, out_node = graph.get_input_node(), graph.get_output_node()
keep = {in_node.get_full_name(), out_node.get_full_name()}
for n in [n for n in graph.nodes if n.get_full_name() not in keep]:
    graph.remove_node(n)
print("cleared; nodes:", len(graph.nodes))
in_node.set_node_position(-2400, -700)
out_node.set_node_position(2600, 300)

V, R = unreal.Vector, unreal.Rotator

def add(cls, x, y, **props):
    node, settings = graph.add_node_of_type(cls)
    node.set_node_position(x, y)
    for k, v in props.items():
        settings.set_editor_property(k, v)
    return node, settings

def tag(prev, x, y, name):
    n, _ = add(unreal.PCGAddTagSettings, x, y, tags_to_add=name)
    prev.add_edge_to("Out", n, "In")
    return n

def spawner(prev, x, y, entries):
    """entries: [(static_mesh, weight), ...]"""
    n, s = add(unreal.PCGStaticMeshSpawnerSettings, x, y)
    s.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    sel = s.get_editor_property("mesh_selector_instance")
    built = []
    for sm, w in entries:
        e = unreal.PCGMeshSelectorWeightedEntry()
        e.set_editor_property("weight", w)
        d = e.get_editor_property("descriptor")
        d.set_editor_property("static_mesh", sm)
        e.set_editor_property("descriptor", d)
        built.append(e)
    sel.set_editor_property("mesh_entries", built)
    prev.add_edge_to("Out", n, "In")
    n.add_edge_to("Out", out_node, "Out")
    return n

# ================= ROADS =================
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
# drop coincident points at intersections (z-fighting with real plates)
n_dedup, s_dedup = add(unreal.PCGSelfPruningSettings, -1500, -500)
pp = s_dedup.get_editor_property("parameters")
pp.set_editor_property("pruning_type", unreal.PCGSelfPruningType.REMOVE_DUPLICATES)
s_dedup.set_editor_property("parameters", pp)
n_roads.add_edge_to("Out", n_dedup, "In")
t_road = tag(n_dedup, 1800, -500, "Road")
spawner(t_road, 2200, -500, [(M_ROAD, 1)])

# ================= CIVIC PLOTS =================
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
n_plot_b, _ = add(unreal.PCGBoundsModifierSettings, -1200, -280,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-1300.0, -1300.0, -2.0), bounds_max=V(1300.0, 1300.0, 25.0))
n_civ_pick.add_edge_to("Out", n_plot_b, "In")
t_plot = tag(n_plot_b, 1800, -280, "CivicPlot")
spawner(t_plot, 2200, -280, [(M_PLOT, 1)])

n_civ_split, _ = add(unreal.PCGDensityNoiseSettings, -900, -160,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0,
                     seed=1337)
n_civ_pick.add_edge_to("Out", n_civ_split, "In")

n_school_f, _ = add(unreal.PCGDensityFilterSettings, -600, -220, lower_bound=0.0, upper_bound=0.5)
n_civ_split.add_edge_to("Out", n_school_f, "In")
n_school_x, _ = add(unreal.PCGTransformPointsSettings, -300, -220,
                    rotation_min=R(0.0, 0.0, -90.0), rotation_max=R(0.0, 0.0, 90.0),
                    uniform_scale=False,
                    scale_min=V(0.85, 0.85, 0.9), scale_max=V(1.1, 1.1, 1.2))
n_school_f.add_edge_to("Out", n_school_x, "In")
t_school = tag(n_school_x, 1800, -220, "School")
spawner(t_school, 2200, -220, [(M_SCHOOL, 1)])

n_hosp_f, _ = add(unreal.PCGDensityFilterSettings, -600, -100, lower_bound=0.5, upper_bound=1.0)
n_civ_split.add_edge_to("Out", n_hosp_f, "In")
n_hosp_x, _ = add(unreal.PCGTransformPointsSettings, -300, -100,
                  rotation_min=R(0.0, 0.0, 0.0), rotation_max=R(0.0, 0.0, 360.0),
                  uniform_scale=False,
                  scale_min=V(0.8, 0.8, 0.8), scale_max=V(1.05, 1.05, 1.3))
n_hosp_f.add_edge_to("Out", n_hosp_x, "In")
t_hosp = tag(n_hosp_x, 1800, -100, "Hospital")
spawner(t_hosp, 2200, -100, [(M_HOSP, 1)])

# ================= CANDIDATES minus civic =================
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

# ================= COMMERCIAL =================
n_com_f, _ = add(unreal.PCGDensityFilterSettings, -600, 100, lower_bound=0.0, upper_bound=0.42)
n_dist_c.add_edge_to("Out", n_com_f, "In")
# SM_Tower is 350x350x2000 at scale 1 -> z scale 0.75..2.25 = 1500..4500 tall
n_com_x, _ = add(unreal.PCGTransformPointsSettings, -300, 150,
                 offset_min=V(-60.0, -60.0, 0.0), offset_max=V(60.0, 60.0, 0.0),
                 rotation_min=R(0.0, 0.0, -6.0), rotation_max=R(0.0, 0.0, 6.0),
                 uniform_scale=False,
                 scale_min=V(0.9, 0.9, 0.75), scale_max=V(1.15, 1.15, 2.25))
n_com_f.add_edge_to("Out", n_com_x, "In")
t_com = tag(n_com_x, 1800, 150, "Commercial")
spawner(t_com, 2200, 150, [(M_TOWER, 1)])

# ================= HOUSES =================
n_res_f, _ = add(unreal.PCGDensityFilterSettings, -600, 280, lower_bound=0.42, upper_bound=1.0)
n_dist_c.add_edge_to("Out", n_res_f, "In")
n_res_noise, _ = add(unreal.PCGDensityNoiseSettings, -450, 340,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_res_f.add_edge_to("Out", n_res_noise, "In")
n_res_thin, _ = add(unreal.PCGDensityFilterSettings, -300, 280, lower_bound=0.3, upper_bound=1.0)
n_res_noise.add_edge_to("Out", n_res_thin, "In")
n_res_x, _ = add(unreal.PCGTransformPointsSettings, -100, 340,
                 offset_min=V(-130.0, -130.0, 0.0), offset_max=V(130.0, 130.0, 0.0),
                 rotation_min=R(0.0, 0.0, -14.0), rotation_max=R(0.0, 0.0, 14.0),
                 uniform_scale=False,
                 scale_min=V(0.75, 0.75, 0.85), scale_max=V(1.3, 1.3, 1.4))
n_res_thin.add_edge_to("Out", n_res_x, "In")
t_res = tag(n_res_x, 1800, 280, "House")
spawner(t_res, 2200, 280, [(M_HG, 3), (M_HF, 2)])

# ================= PARK TREES =================
n_tree_noise, _ = add(unreal.PCGDensityNoiseSettings, -900, 460,
                      mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_interior.add_edge_to("Out", n_tree_noise, "In")
n_tree_f, _ = add(unreal.PCGDensityFilterSettings, -600, 460, lower_bound=0.55, upper_bound=1.0)
n_tree_noise.add_edge_to("Out", n_tree_f, "In")
n_tree_x, _ = add(unreal.PCGTransformPointsSettings, -300, 460,
                  offset_min=V(-250.0, -250.0, 0.0), offset_max=V(250.0, 250.0, 0.0),
                  rotation_min=R(0.0, 0.0, 0.0), rotation_max=R(0.0, 0.0, 360.0),
                  uniform_scale=True,
                  scale_min=V(0.6, 0.6, 0.6), scale_max=V(1.5, 1.5, 1.5))
n_tree_f.add_edge_to("Out", n_tree_x, "In")
t_tree = tag(n_tree_x, 1800, 460, "Tree")
spawner(t_tree, 2200, 460, [(M_TR, 3), (M_TC, 2)])

# ================= ROADSIDE =================
def roadside(y, along_step, side_offset, phase, thin_keep, tag_name, entries,
             yaw_ns, yaw_ew, yaw_jitter=0.0, scale_rng=None):
    """NS/EW line grids -> per-orientation offset+facing -> union -> thin -> tag -> spawn.
    yaw_ns/yaw_ew: fixed facing for props along NS/EW roads (absolute)."""
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
                  absolute_offset=True,
                  rotation_min=R(0.0, 0.0, yaw_ns), rotation_max=R(0.0, 0.0, yaw_ns),
                  absolute_rotation=True)
    o_ew, _ = add(unreal.PCGTransformPointsSettings, -1800, y + 60,
                  offset_min=V(phase, side_offset, 0.0), offset_max=V(phase, side_offset, 0.0),
                  absolute_offset=True,
                  rotation_min=R(0.0, 0.0, yaw_ew), rotation_max=R(0.0, 0.0, yaw_ew),
                  absolute_rotation=True)
    g_ns.add_edge_to("Out", o_ns, "In")
    g_ew.add_edge_to("Out", o_ew, "In")
    u, _ = add(unreal.PCGUnionSettings, -1500, y)
    o_ns.add_edge_to("Out", u, "In")
    o_ew.add_edge_to("Out", u, "In")
    prev = u
    if thin_keep < 1.0:
        # Union outputs composite spatial data; AttributeNoise can't access
        # $Density on it ("Attribute '$Density' was not found"). Collapse to
        # concrete points first.
        topoint, _ = add(unreal.PCGConvertToPointDataSettings, -1350, y)
        prev.add_edge_to("Out", topoint, "In")
        prev = topoint
        nn, _ = add(unreal.PCGDensityNoiseSettings, -1200, y,
                    mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
        prev.add_edge_to("Out", nn, "In")
        nf, _ = add(unreal.PCGDensityFilterSettings, -900, y,
                    lower_bound=1.0 - thin_keep, upper_bound=1.0)
        nn.add_edge_to("Out", nf, "In")
        prev = nf
    if yaw_jitter > 0.0 or scale_rng:
        kw = {}
        if yaw_jitter > 0.0:
            kw.update(rotation_min=R(0.0, 0.0, -yaw_jitter), rotation_max=R(0.0, 0.0, yaw_jitter))
        if scale_rng:
            kw.update(uniform_scale=True,
                      scale_min=V(scale_rng[0], scale_rng[0], scale_rng[0]),
                      scale_max=V(scale_rng[1], scale_rng[1], scale_rng[1]))
        x, _ = add(unreal.PCGTransformPointsSettings, -600, y, **kw)
        prev.add_edge_to("Out", x, "In")
        prev = x
    t = tag(prev, 1800, y, tag_name)
    spawner(t, 2200, y, entries)

# lamps: east/north side, arm (+X local) must face the road
roadside(620, 1500.0, 150.0, 0.0, 1.0, "Light", [(M_LAMP, 1)],
         yaw_ns=180.0, yaw_ew=-90.0)
# street trees: west/south side, interleaved with lamps; random yaw is fine
roadside(800, 1500.0, -150.0, 750.0, 1.0, "StreetTree", [(M_TC, 3), (M_TR, 1)],
         yaw_ns=0.0, yaw_ew=0.0, yaw_jitter=180.0, scale_rng=(0.7, 1.35))
# benches: east/north side, back (+Y local) away from road -> face the road
roadside(980, 3000.0, 190.0, 375.0, 0.45, "Bench", [(M_BENCH, 1)],
         yaw_ns=-90.0, yaw_ew=0.0, yaw_jitter=6.0)
# bins: west/south side
roadside(1160, 3000.0, -190.0, -650.0, 0.35, "Bin", [(M_BIN, 1)],
         yaw_ns=0.0, yaw_ew=0.0)

# ================= BUS STOPS =================
n_ix, _ = add(unreal.PCGCreatePointsGridSettings, -2100, 1340,
              grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
              cell_size=V(BLOCK, BLOCK, 100.0),
              coordinate_space=unreal.PCGCoordinateSpace.WORLD,
              set_points_bounds=False)
# NE of intersections; opening (+Y local) turned toward the EW road to the south
n_ix_o, _ = add(unreal.PCGTransformPointsSettings, -1800, 1340,
                offset_min=V(280.0, 280.0, 0.0), offset_max=V(280.0, 280.0, 0.0),
                absolute_offset=True,
                rotation_min=R(0.0, 0.0, 180.0), rotation_max=R(0.0, 0.0, 180.0),
                absolute_rotation=True)
n_ix.add_edge_to("Out", n_ix_o, "In")
n_bus_noise, _ = add(unreal.PCGDensityNoiseSettings, -1500, 1340,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_ix_o.add_edge_to("Out", n_bus_noise, "In")
n_bus_f, _ = add(unreal.PCGDensityFilterSettings, -1200, 1340, lower_bound=0.55, upper_bound=1.0)
n_bus_noise.add_edge_to("Out", n_bus_f, "In")
t_bus = tag(n_bus_f, 1800, 1340, "BusStop")
spawner(t_bus, 2200, 1340, [(M_BUS, 1)])

ok = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("graph saved:", ok, "total nodes:", len(graph.nodes))
mcp_result = {"saved": bool(ok), "node_count": len(graph.nodes)}
