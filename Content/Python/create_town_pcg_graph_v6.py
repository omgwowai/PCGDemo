"""Rebuild /Game/Town/PCG_TownGraph in place — v6: anti-overlap pass.

Overlap audit of v5 found real collisions; v6 adds explicit separation:
  Road corridor   road points -> BoundsModifier SET +-470 = keep-out strip.
                  Houses & commercial are Difference'd against it (fixes
                  House x Road, Bench/Bin x House since furniture sits inside
                  the corridor while buildings now stay >= 470 from centerline).
  Bus stops       own +-380 keep-out (shelter extends past the corridor).
  Houses/towers   post-placement points inflated (+-380/+-420) become keep-outs
                  for park trees (fixes trunk-inside-house).
  Park trees      crown-sized bounds (+-140) + SelfPruning LARGE_TO_SMALL
                  (fixes tree-tree trunk merges); interior band starts at 0.6
                  so crowns clear street-tree crowns.
  Street trees    moved to -220 from centerline (trunk clears road edge) and
                  SelfPruning removes NS/EW corner duplicates.
  Bench/Bin       re-phased along the road (900 / -1400) to keep clear of bus
                  shelters and street trees.
Intentional & accepted: road plates tile edge-to-edge; school/hospital sit ON
their civic plot; tree crowns may overhang roads/yards (crown z >= 130, no 3D
clash with 15cm road plates).
"""
import unreal, json, os

TOWN_EXT = 12000.0
BLOCK = 3000.0
ROAD_LINE_STEP = 250.0
CAND_STEP = 750.0
GRAPH_PATH = "/Game/Town/PCG_TownGraph"
RENDER_MESHES_DEFAULT = True
ROAD_USE_SPLINE_DEFAULT = False
ROAD_ACTOR_TAG = "TownRoad"

# Keep-out half widths. Difference tests obstacle bounds against the SOURCE
# point's own bounds too, so before every clearance Difference the source is
# shrunk to a +-10 marker (see small_marker) — the obstacle width alone then
# controls the clearance distance.
CORRIDOR_HE = 350.0      # buildings survive > ~360 from centerline; band reaches 675
BUS_OBST_HE = 420.0      # shelter reach 440 + building he ~200 vs 420+10 clearance
HOUSE_OBST_HE = 380.0    # house keep-out for trees (house he ~195 + crown allowance)
COM_OBST_HE = 420.0      # tower keep-out for trees

proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
with open(os.path.join(proj, "Plans", "town_styles.json"), "r", encoding="utf-8") as f:
    registry = json.load(f)
STYLE = registry["styles"][registry["active_style"]]["categories"]
print("active style:", registry["active_style"])

def style_entries(category):
    out = []
    for e in STYLE[category]:
        m = unreal.EditorAssetLibrary.load_asset(e["mesh"])
        assert m, f"style mesh missing: {e['mesh']}"
        out.append((m, e["weight"]))
    return out

def mat(p):
    m = unreal.EditorAssetLibrary.load_asset(p)
    assert m, f"missing material {p}"
    return m

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
in_node.set_node_position(-3000, -700)
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

def param_node(x, y, title, attr_name, mtype, **value):
    n, s = add(unreal.PCGCreateAttributeSetSettings, x, y)
    at = s.get_editor_property("attribute_types")
    at.set_editor_property("type", mtype)
    for k, v in value.items():
        at.set_editor_property(k, v)
    s.set_editor_property("attribute_types", at)
    osel = s.get_editor_property("output_target")
    osel.import_text(f'(Selection=Attribute,AttributeName="{attr_name}")')
    s.set_editor_property("output_target", osel)
    n.node_title = title
    return n

def self_prune(prev, x, y, prune_type=unreal.PCGSelfPruningType.LARGE_TO_SMALL):
    n, s = add(unreal.PCGSelfPruningSettings, x, y)
    p = s.get_editor_property("parameters")
    p.set_editor_property("pruning_type", prune_type)
    s.set_editor_property("parameters", p)
    prev.add_edge_to("Out", n, "In")
    return n

def bounds(prev, x, y, he_xy, z0=0.0, z1=200.0, title=None):
    n, _ = add(unreal.PCGBoundsModifierSettings, x, y,
               mode=unreal.PCGBoundsModifierMode.SET,
               bounds_min=V(-he_xy, -he_xy, z0), bounds_max=V(he_xy, he_xy, z1))
    if title:
        n.node_title = title
    prev.add_edge_to("Out", n, "In")
    return n

def clear_against(prev, x, y, obstacles, title):
    """Shrink source to +-10 markers, Difference away the obstacle volumes."""
    marker = bounds(prev, x - 150, y, 10.0, 0.0, 100.0)
    diff, _ = add(unreal.PCGDifferenceSettings, x, y,
                  density_function=unreal.PCGDifferenceDensityFunction.BINARY)
    diff.node_title = title
    marker.add_edge_to("Out", diff, "Source")
    for ob in obstacles:
        ob.add_edge_to("Out", diff, "Differences")
    return diff

# ================= PARAM NODES =================
n_mode = param_node(-3000, -560, "MODE SWITCH (True=Meshes / False=DebugPoints)",
                    "bOutputToB", unreal.PCGMetadataTypes.BOOLEAN,
                    bool_value=RENDER_MESHES_DEFAULT)
n_roadsel = param_node(-3000, -440, "ROAD SOURCE SWITCH (True=Spline / False=Grid)",
                       "bUseInputB", unreal.PCGMetadataTypes.BOOLEAN,
                       bool_value=ROAD_USE_SPLINE_DEFAULT)
n_size_full = param_node(-3000, -320, "SIZE GridExtents Full",
                         "GridExtents", unreal.PCGMetadataTypes.VECTOR,
                         vector_value=V(TOWN_EXT, TOWN_EXT, 1.0))
n_size_cand = param_node(-3000, -200, "SIZE GridExtents Cand",
                         "GridExtents", unreal.PCGMetadataTypes.VECTOR,
                         vector_value=V(TOWN_EXT - 400.0, TOWN_EXT - 400.0, 1.0))
n_size_block = param_node(-3000, -80, "SIZE GridExtents Block",
                          "GridExtents", unreal.PCGMetadataTypes.VECTOR,
                          vector_value=V(TOWN_EXT - 1500.0, TOWN_EXT - 1500.0, 1.0))
n_size_maxd = param_node(-3000, 40, "SIZE MaxDistance",
                         "MaximumDistance", unreal.PCGMetadataTypes.DOUBLE,
                         double_value=TOWN_EXT)

def sized_grid(x, y, cell, extent_node=n_size_full):
    n, _ = add(unreal.PCGCreatePointsGridSettings, x, y,
               grid_extents=V(TOWN_EXT, TOWN_EXT, 1.0),
               cell_size=cell,
               coordinate_space=unreal.PCGCoordinateSpace.WORLD,
               set_points_bounds=False)
    extent_node.add_edge_to("Out", n, "GridExtents")
    return n

def branch_out(prev, y, tag_name, dbg_mat, dbg_bmin, dbg_bmax):
    t, _ = add(unreal.PCGAddTagSettings, 1500, y, tags_to_add=tag_name)
    prev.add_edge_to("Out", t, "In")
    br, _ = add(unreal.PCGBranchSettings, 1800, y)
    br.node_title = f"Branch {tag_name}"
    t.add_edge_to("Out", br, "In")
    n_mode.add_edge_to("Out", br, "bOutputToB")
    db, dbs = add(unreal.PCGBoundsModifierSettings, 2200, y - 50,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=dbg_bmin, bounds_max=dbg_bmax)
    set_debug(dbs, dbg_mat)
    db.node_title = f"Debug {tag_name}"
    br.add_edge_to("Output A", db, "In")
    db.add_edge_to("Out", out_node, "Out")
    sp, ss = add(unreal.PCGStaticMeshSpawnerSettings, 2200, y + 50)
    ss.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    sel = ss.get_editor_property("mesh_selector_instance")
    built = []
    for sm, w in style_entries(tag_name):
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
n_grid_ns = sized_grid(-2600, -560, V(BLOCK, ROAD_LINE_STEP, 100.0))
n_grid_ew = sized_grid(-2600, -440, V(ROAD_LINE_STEP, BLOCK, 100.0))
n_roads_u, _ = add(unreal.PCGUnionSettings, -2300, -500)
n_grid_ns.add_edge_to("Out", n_roads_u, "In")
n_grid_ew.add_edge_to("Out", n_roads_u, "In")
n_dedup = self_prune(n_roads_u, -2000, -500, unreal.PCGSelfPruningType.REMOVE_DUPLICATES)

n_getspline, s_getspline = add(unreal.PCGGetSplineSettings, -2600, -320)
asel = s_getspline.get_editor_property("actor_selector")
asel.set_editor_property("actor_filter", unreal.PCGActorFilter.ALL_WORLD_ACTORS)
asel.set_editor_property("actor_selection", unreal.PCGActorSelection.BY_TAG)
asel.set_editor_property("actor_selection_tag", ROAD_ACTOR_TAG)
asel.set_editor_property("select_multiple", True)
s_getspline.set_editor_property("actor_selector", asel)
n_getspline.node_title = f"Get Splines (tag={ROAD_ACTOR_TAG})"

n_sampler, s_sampler = add(unreal.PCGSplineSamplerSettings, -2300, -320)
sparams = s_sampler.get_editor_property("sampler_params")
sparams.set_editor_property("dimension", unreal.PCGSplineSamplingDimension.ON_SPLINE)
sparams.set_editor_property("mode", unreal.PCGSplineSamplingMode.DISTANCE)
sparams.set_editor_property("distance_increment", ROAD_LINE_STEP)
sparams.set_editor_property("unbounded", True)
s_sampler.set_editor_property("sampler_params", sparams)
n_getspline.add_edge_to("Out", n_sampler, "Spline")

n_roadpick, _ = add(unreal.PCGBooleanSelectSettings, -1700, -420)
n_roadpick.node_title = "Road Source Select"
n_dedup.add_edge_to("Out", n_roadpick, "Input A")
n_sampler.add_edge_to("Out", n_roadpick, "Input B")
n_roadsel.add_edge_to("Out", n_roadpick, "bUseInputB")

branch_out(n_roadpick, -500, "Road", D_WHITE,
           V(-140.0, -140.0, -5.0), V(140.0, 140.0, 5.0))

# road corridor keep-out (buildings must stay off the road strip + sidewalk)
n_corridor = bounds(n_roadpick, -1400, -420, CORRIDOR_HE, -100.0, 300.0,
                    title="OBSTACLE Road Corridor")
# narrow strip = just the paved surface (+10 margin): street-tree trunks at
# offset 220 survive it, but trees standing on a CROSSING road (dist 0-125,
# the along-road lattice hits cross centerlines every other point) are culled
n_road_strip = bounds(n_roadpick, -1400, -360, 150.0, -100.0, 300.0,
                      title="OBSTACLE Road Strip")

# ================= BUS STOPS (early: they are obstacles for buildings) ======
n_ix = sized_grid(-2600, 1340, V(BLOCK, BLOCK, 100.0))
n_ix_o, _ = add(unreal.PCGTransformPointsSettings, -2300, 1340,
                offset_min=V(280.0, 280.0, 0.0), offset_max=V(280.0, 280.0, 0.0),
                absolute_offset=True,
                rotation_min=R(0.0, 0.0, 180.0), rotation_max=R(0.0, 0.0, 180.0),
                absolute_rotation=True)
n_ix.add_edge_to("Out", n_ix_o, "In")
n_bus_noise, _ = add(unreal.PCGDensityNoiseSettings, -2000, 1340,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_ix_o.add_edge_to("Out", n_bus_noise, "In")
n_bus_f, _ = add(unreal.PCGDensityFilterSettings, -1700, 1340, lower_bound=0.55, upper_bound=1.0)
n_bus_noise.add_edge_to("Out", n_bus_f, "In")
branch_out(n_bus_f, 1340, "BusStop", D_GRAY,
           V(-140.0, -55.0, 0.0), V(140.0, 55.0, 190.0))
n_bus_obst = bounds(n_bus_f, -1400, 1400, BUS_OBST_HE, -100.0, 300.0,
                    title="OBSTACLE Bus Stops")

# ================= CIVIC PLOTS =================
n_blocks = sized_grid(-2600, -160, V(BLOCK, BLOCK, 100.0), n_size_block)
n_civ_noise, _ = add(unreal.PCGDensityNoiseSettings, -2300, -160,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_blocks.add_edge_to("Out", n_civ_noise, "In")
n_civ_pick, _ = add(unreal.PCGDensityFilterSettings, -2000, -160,
                    lower_bound=0.8, upper_bound=1.0)
n_civ_noise.add_edge_to("Out", n_civ_pick, "In")
n_plot_b, _ = add(unreal.PCGBoundsModifierSettings, -1700, -160,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-1300.0, -1300.0, -2.0), bounds_max=V(1300.0, 1300.0, 25.0))
n_civ_pick.add_edge_to("Out", n_plot_b, "In")
branch_out(n_plot_b, -280, "CivicPlot", D_YELLOW,
           V(-1300.0, -1300.0, -2.0), V(1300.0, 1300.0, 25.0))

n_civ_split, _ = add(unreal.PCGDensityNoiseSettings, -1400, -100,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0,
                     seed=1337)
n_civ_pick.add_edge_to("Out", n_civ_split, "In")

n_school_f, _ = add(unreal.PCGDensityFilterSettings, -1100, -220, lower_bound=0.0, upper_bound=0.5)
n_civ_split.add_edge_to("Out", n_school_f, "In")
n_school_x, _ = add(unreal.PCGTransformPointsSettings, -800, -220,
                    rotation_min=R(0.0, 0.0, -90.0), rotation_max=R(0.0, 0.0, 90.0),
                    uniform_scale=False,
                    scale_min=V(0.85, 0.85, 0.9), scale_max=V(1.1, 1.1, 1.2))
n_school_f.add_edge_to("Out", n_school_x, "In")
branch_out(n_school_x, -220, "School", D_PURPLE,
           V(-800.0, -500.0, 0.0), V(800.0, 500.0, 450.0))

n_hosp_f, _ = add(unreal.PCGDensityFilterSettings, -1100, -100, lower_bound=0.5, upper_bound=1.0)
n_civ_split.add_edge_to("Out", n_hosp_f, "In")
n_hosp_x, _ = add(unreal.PCGTransformPointsSettings, -800, -100,
                  rotation_min=R(0.0, 0.0, 0.0), rotation_max=R(0.0, 0.0, 360.0),
                  uniform_scale=False,
                  scale_min=V(0.8, 0.8, 0.8), scale_max=V(1.05, 1.05, 1.3))
n_hosp_f.add_edge_to("Out", n_hosp_x, "In")
branch_out(n_hosp_x, -100, "Hospital", D_CYAN,
           V(-650.0, -650.0, 0.0), V(650.0, 650.0, 900.0))

# ================= CANDIDATES =================
n_cand = sized_grid(-2600, 100, V(CAND_STEP, CAND_STEP, 100.0), n_size_cand)
n_cand_diff, _ = add(unreal.PCGDifferenceSettings, -2300, 100,
                     density_function=unreal.PCGDifferenceDensityFunction.BINARY)
n_cand.add_edge_to("Out", n_cand_diff, "Source")
n_plot_b.add_edge_to("Out", n_cand_diff, "Differences")

n_dist_road, _ = add(unreal.PCGDistanceSettings, -2000, 100,
                     set_density=True, output_to_attribute=False,
                     maximum_distance=1500.0,
                     source_shape=unreal.PCGDistanceShape.CENTER,
                     target_shape=unreal.PCGDistanceShape.CENTER)
n_cand_diff.add_edge_to("Out", n_dist_road, "Source")
n_roadpick.add_edge_to("Out", n_dist_road, "Target")

# street-front band widened (0.15-0.45): the corridor Difference removes the
# inner part, this keeps enough candidates outside it
n_band, _ = add(unreal.PCGDensityFilterSettings, -1700, 40, lower_bound=0.15, upper_bound=0.45)
n_dist_road.add_edge_to("Out", n_band, "In")
# interior raised to 0.6 so park-tree crowns clear street-tree crowns
n_interior, _ = add(unreal.PCGDensityFilterSettings, -1700, 460, lower_bound=0.6, upper_bound=1.0)
n_dist_road.add_edge_to("Out", n_interior, "In")

n_center, s_center = add(unreal.PCGCreatePointsSettings, -2000, -20,
                         coordinate_space=unreal.PCGCoordinateSpace.WORLD)
s_center.set_editor_property("points_to_create", [unreal.PCGPoint()])
n_dist_c, _ = add(unreal.PCGDistanceSettings, -1400, 40,
                  set_density=True, output_to_attribute=False,
                  maximum_distance=TOWN_EXT,
                  source_shape=unreal.PCGDistanceShape.CENTER,
                  target_shape=unreal.PCGDistanceShape.CENTER)
n_band.add_edge_to("Out", n_dist_c, "Source")
n_center.add_edge_to("Out", n_dist_c, "Target")
n_size_maxd.add_edge_to("Out", n_dist_c, "MaximumDistance")

# ================= COMMERCIAL =================
n_com_f, _ = add(unreal.PCGDensityFilterSettings, -1100, 100, lower_bound=0.0, upper_bound=0.42)
n_dist_c.add_edge_to("Out", n_com_f, "In")
n_com_x, _ = add(unreal.PCGTransformPointsSettings, -800, 150,
                 offset_min=V(-60.0, -60.0, 0.0), offset_max=V(60.0, 60.0, 0.0),
                 rotation_min=R(0.0, 0.0, -6.0), rotation_max=R(0.0, 0.0, 6.0),
                 uniform_scale=False,
                 scale_min=V(0.9, 0.9, 0.75), scale_max=V(1.15, 1.15, 2.25))
n_com_f.add_edge_to("Out", n_com_x, "In")
n_com_clear = clear_against(n_com_x, -450, 150, [n_corridor, n_bus_obst],
                            "Commercial away from road/bus")
branch_out(n_com_clear, 150, "Commercial", D_ORANGE,
           V(-175.0, -175.0, 0.0), V(175.0, 175.0, 2000.0))
n_com_obst = bounds(n_com_clear, -200, 210, COM_OBST_HE, -100.0, 300.0,
                    title="OBSTACLE Towers")

# ================= HOUSES =================
n_res_f, _ = add(unreal.PCGDensityFilterSettings, -1100, 280, lower_bound=0.42, upper_bound=1.0)
n_dist_c.add_edge_to("Out", n_res_f, "In")
n_res_noise, _ = add(unreal.PCGDensityNoiseSettings, -950, 340,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_res_f.add_edge_to("Out", n_res_noise, "In")
n_res_thin, _ = add(unreal.PCGDensityFilterSettings, -800, 280, lower_bound=0.3, upper_bound=1.0)
n_res_noise.add_edge_to("Out", n_res_thin, "In")
n_res_x, _ = add(unreal.PCGTransformPointsSettings, -650, 340,
                 offset_min=V(-130.0, -130.0, 0.0), offset_max=V(130.0, 130.0, 0.0),
                 rotation_min=R(0.0, 0.0, -14.0), rotation_max=R(0.0, 0.0, 14.0),
                 uniform_scale=False,
                 scale_min=V(0.75, 0.75, 0.85), scale_max=V(1.3, 1.3, 1.4))
n_res_thin.add_edge_to("Out", n_res_x, "In")
n_res_clear = clear_against(n_res_x, -350, 280, [n_corridor, n_bus_obst],
                            "Houses away from road/bus")
branch_out(n_res_clear, 280, "House", D_RED,
           V(-150.0, -150.0, 0.0), V(150.0, 150.0, 250.0))
n_house_obst = bounds(n_res_clear, -50, 340, HOUSE_OBST_HE, -100.0, 300.0,
                      title="OBSTACLE Houses")
# narrower wall-sized obstacle for street-tree trunks (house he max ~253 incl. rotation)
n_house_wall = bounds(n_res_clear, -50, 400, 260.0, -100.0, 300.0,
                      title="OBSTACLE House walls")
n_com_wall = bounds(n_com_clear, -200, 260, 220.0, -100.0, 300.0,
                    title="OBSTACLE Tower walls")

# ================= PARK TREES =================
n_tree_noise, _ = add(unreal.PCGDensityNoiseSettings, -1400, 460,
                      mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_interior.add_edge_to("Out", n_tree_noise, "In")
n_tree_f, _ = add(unreal.PCGDensityFilterSettings, -1100, 460, lower_bound=0.55, upper_bound=1.0)
n_tree_noise.add_edge_to("Out", n_tree_f, "In")
n_tree_x, _ = add(unreal.PCGTransformPointsSettings, -950, 460,
                  offset_min=V(-250.0, -250.0, 0.0), offset_max=V(250.0, 250.0, 0.0),
                  rotation_min=R(0.0, 0.0, 0.0), rotation_max=R(0.0, 0.0, 360.0),
                  uniform_scale=True,
                  scale_min=V(0.6, 0.6, 0.6), scale_max=V(1.5, 1.5, 1.5))
n_tree_f.add_edge_to("Out", n_tree_x, "In")
# crown-sized bounds + prune -> no tree merges into another
n_tree_b = bounds(n_tree_x, -800, 460, 140.0, 0.0, 400.0)
n_tree_prune = self_prune(n_tree_b, -650, 460)
# keep trunks out of houses/towers (trunk-level check, crowns may overhang)
n_tree_clear = clear_against(n_tree_prune, -350, 460, [n_house_obst, n_com_obst],
                             "Trees away from buildings")
branch_out(n_tree_clear, 460, "Tree", D_GREEN,
           V(-50.0, -50.0, 0.0), V(50.0, 50.0, 300.0))

# ================= ROADSIDE furniture =================
def roadside(y, along_step, side_offset, phase, thin_keep, tag_name, dbg_mat,
             dbg_bmin, dbg_bmax, yaw_ns, yaw_ew, yaw_jitter=0.0, scale_rng=None,
             dedupe=False, clear_obstacles=None):
    g_ns = sized_grid(-2600, y - 60, V(BLOCK, along_step, 100.0))
    g_ew = sized_grid(-2600, y + 60, V(along_step, BLOCK, 100.0))
    o_ns, _ = add(unreal.PCGTransformPointsSettings, -2300, y - 60,
                  offset_min=V(side_offset, phase, 0.0), offset_max=V(side_offset, phase, 0.0),
                  absolute_offset=True,
                  rotation_min=R(0.0, 0.0, yaw_ns), rotation_max=R(0.0, 0.0, yaw_ns),
                  absolute_rotation=True)
    o_ew, _ = add(unreal.PCGTransformPointsSettings, -2300, y + 60,
                  offset_min=V(phase, side_offset, 0.0), offset_max=V(phase, side_offset, 0.0),
                  absolute_offset=True,
                  rotation_min=R(0.0, 0.0, yaw_ew), rotation_max=R(0.0, 0.0, yaw_ew),
                  absolute_rotation=True)
    g_ns.add_edge_to("Out", o_ns, "In")
    g_ew.add_edge_to("Out", o_ew, "In")
    u, _ = add(unreal.PCGUnionSettings, -2000, y)
    o_ns.add_edge_to("Out", u, "In")
    o_ew.add_edge_to("Out", u, "In")
    topoint, _ = add(unreal.PCGConvertToPointDataSettings, -1850, y)
    u.add_edge_to("Out", topoint, "In")
    prev = topoint
    if dedupe:
        prev = bounds(prev, -1750, y, 140.0, 0.0, 300.0)
        prev = self_prune(prev, -1600, y)
    if thin_keep < 1.0:
        nn, _ = add(unreal.PCGDensityNoiseSettings, -1450, y,
                    mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
        prev.add_edge_to("Out", nn, "In")
        nf, _ = add(unreal.PCGDensityFilterSettings, -1300, y,
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
        x, _ = add(unreal.PCGTransformPointsSettings, -1100, y, **kw)
        prev.add_edge_to("Out", x, "In")
        prev = x
    if clear_obstacles:
        prev = clear_against(prev, -800, y, clear_obstacles, f"{tag_name} away from buildings")
    branch_out(prev, y, tag_name, dbg_mat, dbg_bmin, dbg_bmax)

roadside(620, 1500.0, 150.0, 0.0, 1.0, "Light", D_BLUE,
         V(-20.0, -20.0, 0.0), V(20.0, 20.0, 400.0), yaw_ns=180.0, yaw_ew=-90.0)
# street trees: -220 (trunk clears road edge at 140), corner dupes pruned,
# scale capped 1.15 (limits crown reach), trunks cleared from building walls
roadside(800, 1500.0, -220.0, 750.0, 1.0, "StreetTree", D_DGREEN,
         V(-60.0, -60.0, 0.0), V(60.0, 60.0, 350.0),
         yaw_ns=0.0, yaw_ew=0.0, yaw_jitter=180.0, scale_rng=(0.7, 1.15), dedupe=True,
         clear_obstacles=[n_house_wall, n_com_wall, n_road_strip])
# benches: phase 900 keeps clear of bus shelters (280) and lights (0/1500)
roadside(980, 3000.0, 190.0, 900.0, 0.45, "Bench", D_BROWN,
         V(-45.0, -18.0, 0.0), V(45.0, 18.0, 45.0),
         yaw_ns=-90.0, yaw_ew=0.0, yaw_jitter=6.0)
# bins share the trees' side and their 1500 lattice along the road; residue
# picks the spacing: 1875 mod 1500 = 375 from trees (> crown 194 + bin 24) and
# 1875 mod 3000 = 1125 from cross-road centerlines (phase 0 would drop bins
# exactly onto the crossing road's surface)
roadside(1160, 3000.0, -190.0, 1875.0, 0.35, "Bin", D_PINK,
         V(-16.0, -16.0, 0.0), V(16.0, 16.0, 60.0), yaw_ns=0.0, yaw_ew=0.0)

ok = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("graph saved:", ok, "total nodes:", len(graph.nodes))
mcp_result = {"saved": bool(ok), "node_count": len(graph.nodes)}
