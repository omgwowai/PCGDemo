"""Rebuild /Game/Town/PCG_TownGraph in place — v4: in-graph render-mode switch.

One CreateAttributeSet node ("MODE SWITCH") holds a bool attribute bOutputToB.
Every category ends in: AddTags -> Branch (param pin bOutputToB <- switch)
  Output A (bOutputToB=False) -> BoundsModifier with debug viz  = DEBUG POINTS
  Output B (bOutputToB=True)  -> PCGStaticMeshSpawner           = REAL MESHES
Toggle at runtime with set_town_render_mode.py (flips the switch node's bool).

Categories: Road, CivicPlot, School, Hospital, Commercial, House, Tree,
Light, StreetTree, Bench, Bin, BusStop.
"""
import unreal

TOWN_EXT = 12000.0
BLOCK = 3000.0
ROAD_LINE_STEP = 250.0
CAND_STEP = 750.0
GRAPH_PATH = "/Game/Town/PCG_TownGraph"
MESH_DIR = "/Game/Town/Meshes"
RENDER_MESHES_DEFAULT = True

def mesh(name):
    m = unreal.EditorAssetLibrary.load_asset(f"{MESH_DIR}/{name}")
    assert m, f"missing mesh {name}"
    return m

def mat(p):
    m = unreal.EditorAssetLibrary.load_asset(p)
    assert m, f"missing material {p}"
    return m

M_ROAD, M_PLOT = mesh("SM_RoadPlate"), mesh("SM_PlotPlate")
M_TOWER, M_HG, M_HF = mesh("SM_Tower"), mesh("SM_HouseGable"), mesh("SM_HouseFlat")
M_SCHOOL, M_HOSP = mesh("SM_SchoolL"), mesh("SM_HospitalCross")
M_TR, M_TC = mesh("SM_TreeRound"), mesh("SM_TreeConifer")
M_LAMP, M_BENCH, M_BIN, M_BUS = mesh("SM_LampPost"), mesh("SM_Bench"), mesh("SM_Bin"), mesh("SM_BusShelter")

D_WHITE  = mat("/PCG/DebugObjects/PCG_DebugWhite")
D_ORANGE = mat("/PCG/DebugObjects/PCG_DebugOrange")
D_RED    = mat("/PCG/DebugObjects/PCG_DebugRed")
D_GREEN  = mat("/PCG/DebugObjects/PCG_DebugGreen")
D_BLUE   = mat("/PCG/DebugObjects/PCG_DebugBlue")
D_YELLOW = mat("/Game/Town/DebugPalette/MI_Debug_Yellow")
D_PURPLE = mat("/Game/Town/DebugPalette/MI_Debug_Purple")
D_CYAN   = mat("/Game/Town/DebugPalette/MI_Debug_Cyan")
D_BROWN  = mat("/Game/Town/DebugPalette/MI_Debug_Brown")
D_DGREEN = mat("/Game/Town/DebugPalette/MI_Debug_DarkGreen")
D_GRAY   = mat("/Game/Town/DebugPalette/MI_Debug_Gray")
D_PINK   = mat("/Game/Town/DebugPalette/MI_Debug_Pink")

graph = unreal.EditorAssetLibrary.load_asset(GRAPH_PATH)
assert graph, "graph missing"
in_node, out_node = graph.get_input_node(), graph.get_output_node()
keep = {in_node.get_full_name(), out_node.get_full_name()}
for n in [n for n in graph.nodes if n.get_full_name() not in keep]:
    graph.remove_node(n)
print("cleared; nodes:", len(graph.nodes))
in_node.set_node_position(-2400, -700)
out_node.set_node_position(3000, 300)

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

# ================= MODE SWITCH =================
n_switch, s_switch = add(unreal.PCGCreateAttributeSetSettings, -2400, -560)
at = s_switch.get_editor_property("attribute_types")
at.set_editor_property("type", unreal.PCGMetadataTypes.BOOLEAN)
at.set_editor_property("bool_value", RENDER_MESHES_DEFAULT)
s_switch.set_editor_property("attribute_types", at)
osel = s_switch.get_editor_property("output_target")
osel.import_text('(Selection=Attribute,AttributeName="bOutputToB")')
s_switch.set_editor_property("output_target", osel)
n_switch.node_title = "MODE SWITCH (True=Meshes / False=DebugPoints)"

def branch_out(prev, y, tag_name, dbg_mat, dbg_bmin, dbg_bmax, entries):
    """AddTags -> Branch(switch) -> A: debug bounds viz / B: mesh spawner."""
    t, _ = add(unreal.PCGAddTagSettings, 1500, y, tags_to_add=tag_name)
    prev.add_edge_to("Out", t, "In")
    br, _ = add(unreal.PCGBranchSettings, 1800, y)
    br.node_title = f"Branch {tag_name}"
    t.add_edge_to("Out", br, "In")
    n_switch.add_edge_to("Out", br, "bOutputToB")
    # A: debug points (box shape + color)
    db, dbs = add(unreal.PCGBoundsModifierSettings, 2200, y - 50,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=dbg_bmin, bounds_max=dbg_bmax)
    set_debug(dbs, dbg_mat)
    db.node_title = f"Debug {tag_name}"
    br.add_edge_to("Output A", db, "In")
    db.add_edge_to("Out", out_node, "Out")
    # B: real meshes
    sp, ss = add(unreal.PCGStaticMeshSpawnerSettings, 2200, y + 50)
    ss.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    sel = ss.get_editor_property("mesh_selector_instance")
    built = []
    for sm, w in entries:
        e = unreal.PCGMeshSelectorWeightedEntry()
        e.set_editor_property("weight", w)
        d = e.get_editor_property("descriptor")
        d.set_editor_property("static_mesh", sm)
        e.set_editor_property("descriptor", d)
        built.append(e)
    sel.set_editor_property("mesh_entries", built)
    sp.node_title = f"Spawn {tag_name}"
    br.add_edge_to("Output B", sp, "In")
    sp.add_edge_to("Out", out_node, "Out")

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
n_dedup, s_dedup = add(unreal.PCGSelfPruningSettings, -1500, -500)
pp = s_dedup.get_editor_property("parameters")
pp.set_editor_property("pruning_type", unreal.PCGSelfPruningType.REMOVE_DUPLICATES)
s_dedup.set_editor_property("parameters", pp)
n_roads.add_edge_to("Out", n_dedup, "In")
branch_out(n_dedup, -500, "Road", D_WHITE,
           V(-140.0, -140.0, -5.0), V(140.0, 140.0, 5.0), [(M_ROAD, 1)])

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
branch_out(n_plot_b, -280, "CivicPlot", D_YELLOW,
           V(-1300.0, -1300.0, -2.0), V(1300.0, 1300.0, 25.0), [(M_PLOT, 1)])

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
branch_out(n_school_x, -220, "School", D_PURPLE,
           V(-800.0, -500.0, 0.0), V(800.0, 500.0, 450.0), [(M_SCHOOL, 1)])

n_hosp_f, _ = add(unreal.PCGDensityFilterSettings, -600, -100, lower_bound=0.5, upper_bound=1.0)
n_civ_split.add_edge_to("Out", n_hosp_f, "In")
n_hosp_x, _ = add(unreal.PCGTransformPointsSettings, -300, -100,
                  rotation_min=R(0.0, 0.0, 0.0), rotation_max=R(0.0, 0.0, 360.0),
                  uniform_scale=False,
                  scale_min=V(0.8, 0.8, 0.8), scale_max=V(1.05, 1.05, 1.3))
n_hosp_f.add_edge_to("Out", n_hosp_x, "In")
branch_out(n_hosp_x, -100, "Hospital", D_CYAN,
           V(-650.0, -650.0, 0.0), V(650.0, 650.0, 900.0), [(M_HOSP, 1)])

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
n_com_x, _ = add(unreal.PCGTransformPointsSettings, -300, 150,
                 offset_min=V(-60.0, -60.0, 0.0), offset_max=V(60.0, 60.0, 0.0),
                 rotation_min=R(0.0, 0.0, -6.0), rotation_max=R(0.0, 0.0, 6.0),
                 uniform_scale=False,
                 scale_min=V(0.9, 0.9, 0.75), scale_max=V(1.15, 1.15, 2.25))
n_com_f.add_edge_to("Out", n_com_x, "In")
branch_out(n_com_x, 150, "Commercial", D_ORANGE,
           V(-175.0, -175.0, 0.0), V(175.0, 175.0, 2000.0), [(M_TOWER, 1)])

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
branch_out(n_res_x, 280, "House", D_RED,
           V(-150.0, -150.0, 0.0), V(150.0, 150.0, 250.0), [(M_HG, 3), (M_HF, 2)])

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
branch_out(n_tree_x, 460, "Tree", D_GREEN,
           V(-50.0, -50.0, 0.0), V(50.0, 50.0, 300.0), [(M_TR, 3), (M_TC, 2)])

# ================= ROADSIDE =================
def roadside(y, along_step, side_offset, phase, thin_keep, tag_name, dbg_mat,
             dbg_bmin, dbg_bmax, entries, yaw_ns, yaw_ew, yaw_jitter=0.0, scale_rng=None):
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
    branch_out(prev, y, tag_name, dbg_mat, dbg_bmin, dbg_bmax, entries)

roadside(620, 1500.0, 150.0, 0.0, 1.0, "Light", D_BLUE,
         V(-20.0, -20.0, 0.0), V(20.0, 20.0, 400.0), [(M_LAMP, 1)],
         yaw_ns=180.0, yaw_ew=-90.0)
roadside(800, 1500.0, -150.0, 750.0, 1.0, "StreetTree", D_DGREEN,
         V(-60.0, -60.0, 0.0), V(60.0, 60.0, 350.0), [(M_TC, 3), (M_TR, 1)],
         yaw_ns=0.0, yaw_ew=0.0, yaw_jitter=180.0, scale_rng=(0.7, 1.35))
roadside(980, 3000.0, 190.0, 375.0, 0.45, "Bench", D_BROWN,
         V(-45.0, -18.0, 0.0), V(45.0, 18.0, 45.0), [(M_BENCH, 1)],
         yaw_ns=-90.0, yaw_ew=0.0, yaw_jitter=6.0)
roadside(1160, 3000.0, -190.0, -650.0, 0.35, "Bin", D_PINK,
         V(-16.0, -16.0, 0.0), V(16.0, 16.0, 60.0), [(M_BIN, 1)],
         yaw_ns=0.0, yaw_ew=0.0)

# ================= BUS STOPS =================
n_ix, _ = add(unreal.PCGCreatePointsGridSettings, -2100, 1340,
              grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
              cell_size=V(BLOCK, BLOCK, 100.0),
              coordinate_space=unreal.PCGCoordinateSpace.WORLD,
              set_points_bounds=False)
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
branch_out(n_bus_f, 1340, "BusStop", D_GRAY,
           V(-140.0, -55.0, 0.0), V(140.0, 55.0, 190.0), [(M_BUS, 1)])

ok = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("graph saved:", ok, "total nodes:", len(graph.nodes))
mcp_result = {"saved": bool(ok), "node_count": len(graph.nodes)}
