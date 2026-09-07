"""Rebuild /Game/Town/PCG_TownGraph in place — v7: spline-aware placement.

v6 left roadside furniture (lights/trees/benches/bins/bus stops) and civic
plots on the GRID lattice even in spline-road mode, so splines cut straight
through them. v7 makes every road-relative branch follow the selected source:

  Roadside furniture   two paths per category, joined by BooleanSelect on the
                       same bUseInputB switch as the road itself:
                         grid path   = v6 NS/EW lattice (absolute offsets/yaws)
                         spline path = SplineSampler(DISTANCE, step, start_offset
                                       =phase) -> TransformPoints in LOCAL space
                                       (sampled points face the tangent: +X along
                                       road, +Y right side)
  Cross-road safety    every furniture category clears "OBSTACLE Road Strip"
                       (+-150). Lights move 150 -> 175 from centerline so their
                       own-road marker (+-10) survives the 160 cull threshold.
  Same-category        footprint bounds + SelfPruning after the select (crossing
                       splines can double-place furniture near intersections).
  Civic plots          block centers now clear an inflated road obstacle
                       (+-1440 = plot 1300 + road 140): splines wandering
                       through a block relocate its civic plot. Grid roads sit
                       1500 from block centers, so grid mode is unaffected.

All node titles / tags / param-node names are unchanged -> ATownActor works as before.
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

CORRIDOR_HE = 350.0
BUS_OBST_HE = 420.0
HOUSE_OBST_HE = 430.0    # house hx up-to 1.3 scale (195) + tree crown up-to 1.5 (202) clearance
COM_OBST_HE = 560.0      # tower hx 180 * up-to 2.25 scale + tree crown 148 clearance
PLOT_ROAD_HE = 1440.0    # plot half 1300 + road half 140

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
in_node.set_node_position(-7680, -2380)   # (-3200,-700) * (SPREAD_X,SPREAD_Y)
out_node.set_node_position(7200, 1020)     # (3000,300)   * (SPREAD_X,SPREAD_Y)

V, R = unreal.Vector, unreal.Rotator

# Layout spread: multiply every authored node coordinate so node boxes never
# overlap and their connecting wires stay visible in the PCG graph editor.
# Wiring/logic is untouched — only on-canvas positions scale.
SPREAD_X = 2.4
SPREAD_Y = 3.4

def add(cls, x, y, **props):
    node, settings = graph.add_node_of_type(cls)
    node.set_node_position(int(x * SPREAD_X), int(y * SPREAD_Y))
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
n_mode = param_node(-3200, -560, "MODE SWITCH (True=Meshes / False=DebugPoints)",
                    "bOutputToB", unreal.PCGMetadataTypes.BOOLEAN,
                    bool_value=RENDER_MESHES_DEFAULT)
n_roadsel = param_node(-3200, -440, "ROAD SOURCE SWITCH (True=Spline / False=Grid)",
                       "bUseInputB", unreal.PCGMetadataTypes.BOOLEAN,
                       bool_value=ROAD_USE_SPLINE_DEFAULT)
n_size_full = param_node(-3200, -320, "SIZE GridExtents Full",
                         "GridExtents", unreal.PCGMetadataTypes.VECTOR,
                         vector_value=V(TOWN_EXT, TOWN_EXT, 1.0))
n_size_cand = param_node(-3200, -200, "SIZE GridExtents Cand",
                         "GridExtents", unreal.PCGMetadataTypes.VECTOR,
                         vector_value=V(TOWN_EXT - 400.0, TOWN_EXT - 400.0, 1.0))
n_size_block = param_node(-3200, -80, "SIZE GridExtents Block",
                          "GridExtents", unreal.PCGMetadataTypes.VECTOR,
                          vector_value=V(TOWN_EXT - 1500.0, TOWN_EXT - 1500.0, 1.0))
n_size_maxd = param_node(-3200, 40, "SIZE MaxDistance",
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
    db, dbs = add(unreal.PCGBoundsModifierSettings, 2150, y - 120,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=dbg_bmin, bounds_max=dbg_bmax)
    set_debug(dbs, dbg_mat)
    db.node_title = f"Debug {tag_name}"
    br.add_edge_to("Output A", db, "In")
    db.add_edge_to("Out", out_node, "Out")
    sp, ss = add(unreal.PCGStaticMeshSpawnerSettings, 2450, y + 120)
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
n_grid_ns = sized_grid(-2800, -560, V(BLOCK, ROAD_LINE_STEP, 100.0))
n_grid_ew = sized_grid(-2800, -440, V(ROAD_LINE_STEP, BLOCK, 100.0))
n_roads_u, _ = add(unreal.PCGUnionSettings, -2550, -500)
n_grid_ns.add_edge_to("Out", n_roads_u, "In")
n_grid_ew.add_edge_to("Out", n_roads_u, "In")
n_dedup = self_prune(n_roads_u, -2350, -500, unreal.PCGSelfPruningType.REMOVE_DUPLICATES)

n_getspline, s_getspline = add(unreal.PCGGetSplineSettings, -2800, -320)
asel = s_getspline.get_editor_property("actor_selector")
asel.set_editor_property("actor_filter", unreal.PCGActorFilter.ALL_WORLD_ACTORS)
asel.set_editor_property("actor_selection", unreal.PCGActorSelection.BY_TAG)
asel.set_editor_property("actor_selection_tag", ROAD_ACTOR_TAG)
asel.set_editor_property("select_multiple", True)
s_getspline.set_editor_property("actor_selector", asel)
n_getspline.node_title = f"Get Splines (tag={ROAD_ACTOR_TAG})"

def spline_sampled(x, y, step, start_offset=0.0):
    n, s = add(unreal.PCGSplineSamplerSettings, x, y)
    p = s.get_editor_property("sampler_params")
    p.set_editor_property("dimension", unreal.PCGSplineSamplingDimension.ON_SPLINE)
    p.set_editor_property("mode", unreal.PCGSplineSamplingMode.DISTANCE)
    p.set_editor_property("distance_increment", step)
    p.set_editor_property("start_offset", start_offset)
    p.set_editor_property("unbounded", True)
    s.set_editor_property("sampler_params", p)
    n_getspline.add_edge_to("Out", n, "Spline")
    return n

n_sampler = spline_sampled(-2550, -320, ROAD_LINE_STEP)

n_roadpick, _ = add(unreal.PCGBooleanSelectSettings, -2100, -420)
n_roadpick.node_title = "Road Source Select"
n_dedup.add_edge_to("Out", n_roadpick, "Input A")
n_sampler.add_edge_to("Out", n_roadpick, "Input B")
n_roadsel.add_edge_to("Out", n_roadpick, "bUseInputB")

branch_out(n_roadpick, -500, "Road", D_WHITE,
           V(-140.0, -140.0, -5.0), V(140.0, 140.0, 5.0))

n_corridor = bounds(n_roadpick, -1800, -460, CORRIDOR_HE, -100.0, 300.0,
                    title="OBSTACLE Road Corridor")
n_road_strip = bounds(n_roadpick, -1800, -400, 150.0, -100.0, 300.0,
                      title="OBSTACLE Road Strip")
n_road_plot_obst = bounds(n_roadpick, -1800, -340, PLOT_ROAD_HE, -100.0, 300.0,
                          title="OBSTACLE Road for Plots")

# Road-plate footprint is 125x125. Furniture that sits along the road must clear
# the plate inflated by its own half-extent, because plates are sampled every 250
# along the spline: the nearest plate can be offset LONGITUDINALLY, so guarding
# only the perpendicular gap (side_offset) is not enough. Each furniture clears a
# road obstacle inflated by (plate 125 + own long-axis half + margin).
ROAD_PLATE_HE = 125.0
def road_obst_for(he, x, y, title):
    return bounds(n_roadpick, x, y, ROAD_PLATE_HE + he, -100.0, 300.0, title=title)
n_road_obst_light = road_obst_for(64.0, -1800, -280, "OBSTACLE Road+Light")   # lamp hx 54
n_road_obst_bench = road_obst_for(80.0, -1800, -220, "OBSTACLE Road+Bench")   # bench hx 70
n_road_obst_bus   = road_obst_for(175.0, -1800, -160, "OBSTACLE Road+Bus")    # bus hx 160
n_road_obst_bin   = road_obst_for(40.0, -1800, -100, "OBSTACLE Road+Bin")     # bin hx 24
n_road_obst_tree  = road_obst_for(150.0, -1800, -40, "OBSTACLE Road+StreetTree")  # tree hx 135

# ================= ROADSIDE (dual-source) =================
def roadside(y, along_step, side_offset, phase, thin_keep, tag_name, dbg_mat,
             dbg_bmin, dbg_bmax, yaw_ns, yaw_ew, rel_yaw, footprint_he,
             yaw_jitter=0.0, scale_rng=None, clear_obstacles=None):
    """Grid path (NS/EW absolute) + spline path (local-space) -> BooleanSelect.
    rel_yaw: relative yaw for spline points (+X=tangent, +Y=right side).
    footprint_he: bounds for same-category SelfPruning after the select."""
    # grid path
    g_ns = sized_grid(-2800, y - 90, V(BLOCK, along_step, 100.0))
    g_ew = sized_grid(-2800, y + 30, V(along_step, BLOCK, 100.0))
    o_ns, _ = add(unreal.PCGTransformPointsSettings, -2550, y - 90,
                  offset_min=V(side_offset, phase, 0.0), offset_max=V(side_offset, phase, 0.0),
                  absolute_offset=True,
                  rotation_min=R(0.0, 0.0, yaw_ns), rotation_max=R(0.0, 0.0, yaw_ns),
                  absolute_rotation=True)
    o_ew, _ = add(unreal.PCGTransformPointsSettings, -2550, y + 30,
                  offset_min=V(phase, side_offset, 0.0), offset_max=V(phase, side_offset, 0.0),
                  absolute_offset=True,
                  rotation_min=R(0.0, 0.0, yaw_ew), rotation_max=R(0.0, 0.0, yaw_ew),
                  absolute_rotation=True)
    g_ns.add_edge_to("Out", o_ns, "In")
    g_ew.add_edge_to("Out", o_ew, "In")
    u, _ = add(unreal.PCGUnionSettings, -2350, y - 30)
    o_ns.add_edge_to("Out", u, "In")
    o_ew.add_edge_to("Out", u, "In")
    # spline path: sample along splines, then offset/rotate in point-local space
    smp = spline_sampled(-2350, y + 90, along_step, start_offset=phase)
    o_sp, _ = add(unreal.PCGTransformPointsSettings, -2100, y + 90,
                  offset_min=V(0.0, side_offset, 0.0), offset_max=V(0.0, side_offset, 0.0),
                  absolute_offset=False,
                  rotation_min=R(0.0, 0.0, rel_yaw), rotation_max=R(0.0, 0.0, rel_yaw),
                  absolute_rotation=False)
    smp.add_edge_to("Out", o_sp, "In")
    # select
    pick, _ = add(unreal.PCGBooleanSelectSettings, -1850, y)
    pick.node_title = f"{tag_name} Source Select"
    u.add_edge_to("Out", pick, "Input A")
    o_sp.add_edge_to("Out", pick, "Input B")
    n_roadsel.add_edge_to("Out", pick, "bUseInputB")
    # normalize + same-category spacing
    topoint, _ = add(unreal.PCGConvertToPointDataSettings, -1650, y)
    pick.add_edge_to("Out", topoint, "In")
    fb = bounds(topoint, -1500, y, footprint_he, 0.0, 300.0)
    prev = self_prune(fb, -1350, y)
    if thin_keep < 1.0:
        nn, _ = add(unreal.PCGDensityNoiseSettings, -1200, y,
                    mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
        prev.add_edge_to("Out", nn, "In")
        nf, _ = add(unreal.PCGDensityFilterSettings, -1050, y,
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
        x, _ = add(unreal.PCGTransformPointsSettings, -900, y, **kw)
        prev.add_edge_to("Out", x, "In")
        prev = x
    if clear_obstacles:
        prev = clear_against(prev, -650, y, clear_obstacles, f"{tag_name} clearance")
    branch_out(prev, y, tag_name, dbg_mat, dbg_bmin, dbg_bmax)
    return prev

# ================= CIVIC PLOTS (road-aware) =================
n_blocks = sized_grid(-2800, -160, V(BLOCK, BLOCK, 100.0), n_size_block)
n_civ_noise, _ = add(unreal.PCGDensityNoiseSettings, -2550, -160,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0)
n_blocks.add_edge_to("Out", n_civ_noise, "In")
n_civ_pick, _ = add(unreal.PCGDensityFilterSettings, -2350, -160,
                    lower_bound=0.8, upper_bound=1.0)
n_civ_noise.add_edge_to("Out", n_civ_pick, "In")
# relocate plots off wandering splines (grid roads pass at 1500 > 1450 cull)
n_civ_clear = clear_against(n_civ_pick, -2050, -160, [n_road_plot_obst],
                            "Plots away from roads")
n_plot_b, _ = add(unreal.PCGBoundsModifierSettings, -1700, -160,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-1300.0, -1300.0, -2.0), bounds_max=V(1300.0, 1300.0, 25.0))
n_civ_clear.add_edge_to("Out", n_plot_b, "In")
# Inflated plot obstacle for park trees: plot 1300 + tree crown 148 + margin, and
# tall (z 0..500) so a tree marker at z[0..400] fully sits inside it -> Difference
# BINARY reliably culls trees whose crown would overhang a civic plot.
n_plot_tree_obst, _ = add(unreal.PCGBoundsModifierSettings, -1550, -160,
                  mode=unreal.PCGBoundsModifierMode.SET,
                  bounds_min=V(-1500.0, -1500.0, -100.0), bounds_max=V(1500.0, 1500.0, 500.0))
n_civ_clear.add_edge_to("Out", n_plot_tree_obst, "In")
branch_out(n_plot_b, -280, "CivicPlot", D_YELLOW,
           V(-1300.0, -1300.0, -2.0), V(1300.0, 1300.0, 25.0))

n_civ_split, _ = add(unreal.PCGDensityNoiseSettings, -1400, -100,
                     mode=unreal.PCGAttributeNoiseMode.SET, noise_min=0.0, noise_max=1.0,
                     seed=1337)
n_civ_clear.add_edge_to("Out", n_civ_split, "In")

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

# ================= BUS STOPS (after plots: clears them) =================
# Grid path: both road sides every 3000; spline path phase 1150 (clear of
# lights@0/1500, trees@750, benches@900, bins@1875 on the arc-length lattice).
# Bus shelter hx=160 -> road obstacle 125+175=300; offset 320 keeps center out.
n_bus_last = roadside(1340, 3000.0, 320.0, 1150.0, 0.55, "BusStop", D_GRAY,
                      V(-140.0, -55.0, 0.0), V(140.0, 55.0, 190.0),
                      yaw_ns=180.0, yaw_ew=180.0, rel_yaw=180.0, footprint_he=170.0,
                      clear_obstacles=[n_road_obst_bus, n_plot_b])
n_bus_obst = bounds(n_bus_last, -350, 1400, BUS_OBST_HE, -100.0, 300.0,
                    title="OBSTACLE Bus Stops")

# ================= CANDIDATES =================
n_cand = sized_grid(-2800, 100, V(CAND_STEP, CAND_STEP, 100.0), n_size_cand)
n_cand_diff, _ = add(unreal.PCGDifferenceSettings, -2550, 100,
                     density_function=unreal.PCGDifferenceDensityFunction.BINARY)
n_cand.add_edge_to("Out", n_cand_diff, "Source")
n_plot_b.add_edge_to("Out", n_cand_diff, "Differences")

n_dist_road, _ = add(unreal.PCGDistanceSettings, -2350, 100,
                     set_density=True, output_to_attribute=False,
                     maximum_distance=1500.0,
                     source_shape=unreal.PCGDistanceShape.CENTER,
                     target_shape=unreal.PCGDistanceShape.CENTER)
n_cand_diff.add_edge_to("Out", n_dist_road, "Source")
n_roadpick.add_edge_to("Out", n_dist_road, "Target")

n_band, _ = add(unreal.PCGDensityFilterSettings, -1700, 40, lower_bound=0.15, upper_bound=0.45)
n_dist_road.add_edge_to("Out", n_band, "In")
n_interior, _ = add(unreal.PCGDensityFilterSettings, -1700, 460, lower_bound=0.6, upper_bound=1.0)
n_dist_road.add_edge_to("Out", n_interior, "In")

n_center, s_center = add(unreal.PCGCreatePointsSettings, -2350, -20,
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
n_com_wall = bounds(n_com_clear, -200, 260, 220.0, -100.0, 300.0,
                    title="OBSTACLE Tower walls")

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
n_house_wall = bounds(n_res_clear, -50, 400, 340.0, -100.0, 300.0,
                      title="OBSTACLE House walls")

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
n_tree_b = bounds(n_tree_x, -800, 460, 140.0, 0.0, 400.0)
n_tree_prune = self_prune(n_tree_b, -650, 460)
n_tree_clear = clear_against(n_tree_prune, -350, 460, [n_house_obst, n_com_obst, n_plot_tree_obst],
                             "Trees away from buildings")
branch_out(n_tree_clear, 460, "Tree", D_GREEN,
           V(-50.0, -50.0, 0.0), V(50.0, 50.0, 300.0))

# ================= ROADSIDE FURNITURE =================
# side_offset must exceed the inflated road obstacle half-width (ROAD_PLATE_HE +
# own half + margin) so clear_against keeps the item's center marker outside the
# obstacle instead of culling it. Perpendicular gap then also clears the plate.
# lights: 230 from centerline (obstacle 125+64=189 < 230; extra margin covers
# road plates from crossing splines landing diagonally near intersections).
roadside(620, 1500.0, 230.0, 0.0, 1.0, "Light", D_BLUE,
         V(-20.0, -20.0, 0.0), V(20.0, 20.0, 400.0),
         yaw_ns=180.0, yaw_ew=-90.0, rel_yaw=-90.0, footprint_he=60.0,
         clear_obstacles=[n_road_obst_light, n_com_wall, n_house_wall])
roadside(800, 1500.0, -300.0, 750.0, 1.0, "StreetTree", D_DGREEN,
         V(-60.0, -60.0, 0.0), V(60.0, 60.0, 350.0),
         yaw_ns=0.0, yaw_ew=0.0, rel_yaw=0.0, footprint_he=140.0,
         yaw_jitter=180.0, scale_rng=(0.7, 1.15),
         clear_obstacles=[n_house_wall, n_com_wall, n_road_obst_tree, n_plot_tree_obst])
roadside(980, 3000.0, 235.0, 900.0, 0.45, "Bench", D_BROWN,
         V(-45.0, -18.0, 0.0), V(45.0, 18.0, 45.0),
         yaw_ns=-90.0, yaw_ew=0.0, rel_yaw=0.0, footprint_he=80.0,
         yaw_jitter=6.0, clear_obstacles=[n_road_obst_bench])
roadside(1160, 3000.0, -200.0, 1875.0, 0.35, "Bin", D_PINK,
         V(-16.0, -16.0, 0.0), V(16.0, 16.0, 60.0),
         yaw_ns=0.0, yaw_ew=0.0, rel_yaw=0.0, footprint_he=30.0,
         clear_obstacles=[n_road_obst_bin])

ok = unreal.EditorAssetLibrary.save_asset(GRAPH_PATH)
print("graph saved:", ok, "total nodes:", len(graph.nodes))
mcp_result = {"saved": bool(ok), "node_count": len(graph.nodes)}
