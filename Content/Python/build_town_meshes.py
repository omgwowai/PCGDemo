"""Build town prop StaticMesh assets procedurally with GeometryScript (UE5.7
GeometryScript_* libraries). All meshes: Z-up, base pivot at Z=0, cm scale.
Material slots are assigned per part via material IDs, then filled with simple
colored materials created here (parent: engine BasicShapeMaterial-style MIC of
PCG_DebugWhite which is an unlit-ish debug mat -> instead we create MIs of
M_TownColor, a trivial opaque material built here with a Color vector param).

Outputs under /Game/Town/Meshes and /Game/Town/MeshMaterials.
"""
import unreal

MESH_DIR = "/Game/Town/Meshes"
MAT_DIR = "/Game/Town/MeshMaterials"

P  = unreal.GeometryScript_Primitives
M  = unreal.GeometryScript_Materials
NA = unreal.GeometryScript_NewAssetUtils
XF = unreal.GeometryScript_MeshTransforms

BASE = unreal.GeometryScriptPrimitiveOriginMode.BASE
CENTER = unreal.GeometryScriptPrimitiveOriginMode.CENTER

# ---------------- color materials ----------------
# One master opaque material with a Color param + rough param, many MIs.
MASTER_PATH = f"{MAT_DIR}/M_TownColor"

def build_master():
    if unreal.EditorAssetLibrary.does_asset_exist(MASTER_PATH):
        return unreal.EditorAssetLibrary.load_asset(MASTER_PATH)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset("M_TownColor", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    mel = unreal.MaterialEditingLibrary
    node = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
    node.set_editor_property("parameter_name", "Color")
    node.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
    mel.connect_material_property(node, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rnode = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -400, 260)
    rnode.set_editor_property("parameter_name", "Roughness")
    rnode.set_editor_property("default_value", 0.8)
    mel.connect_material_property(rnode, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(MASTER_PATH)
    return mat

MASTER = build_master()

PALETTE = {
    "Asphalt":   (0.16, 0.16, 0.17),
    "Pavement":  (0.55, 0.53, 0.50),
    "GlassBlue": (0.18, 0.35, 0.55),
    "RoofGray":  (0.25, 0.26, 0.28),
    "WallCream": (0.85, 0.78, 0.62),
    "WallBrick": (0.48, 0.22, 0.15),
    "RoofRed":   (0.55, 0.12, 0.10),
    "SchoolTan": (0.78, 0.60, 0.35),
    "HospWhite": (0.90, 0.91, 0.93),
    "HospRed":   (0.80, 0.10, 0.10),
    "TrunkBrown":(0.30, 0.18, 0.08),
    "LeafGreen": (0.12, 0.38, 0.10),
    "LeafDark":  (0.05, 0.25, 0.07),
    "MetalDark": (0.12, 0.12, 0.14),
    "LampWarm":  (1.0, 0.85, 0.45),
    "WoodBench": (0.45, 0.30, 0.15),
    "BinGreen":  (0.10, 0.30, 0.12),
    "ShelterBlue":(0.20, 0.30, 0.45),
}

def get_mi(name):
    path = f"{MAT_DIR}/MI_{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(f"MI_{name}", MAT_DIR, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, MASTER)
    r, g, b = PALETTE[name]
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        mi, "Color", unreal.LinearColor(r, g, b, 1.0))
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_asset(path)
    return mi

# ---------------- mesh builder ----------------
pool = unreal.DynamicMeshPool()

def T(x=0.0, y=0.0, z=0.0, yaw=0.0):
    return unreal.Transform(location=[x, y, z], rotation=[0.0, 0.0, yaw], scale=[1.0, 1.0, 1.0])

class Builder:
    def __init__(self):
        self.mesh = pool.request_mesh()
        M.enable_material_i_ds(self.mesh)
        self.slots = []          # material names in slot order
        self._before = 0
    def _slot(self, mat_name):
        if mat_name in self.slots:
            return self.slots.index(mat_name)
        self.slots.append(mat_name)
        return len(self.slots) - 1
    def _mark(self):
        q = unreal.GeometryScript_MeshQueries
        self._before = q.get_num_triangle_i_ds(self.mesh)
    def _apply(self, mat_name):
        q = unreal.GeometryScript_MeshQueries
        after = q.get_num_triangle_i_ds(self.mesh)
        ids = list(range(self._before, after))
        S = unreal.GeometryScript_MeshSelection
        _, sel = S.convert_index_array_to_mesh_selection(
            self.mesh, ids, unreal.GeometryScriptMeshSelectionType.TRIANGLES)
        M.set_material_id_for_mesh_selection(self.mesh, sel, self._slot(mat_name))
    def box(self, mat, x, y, z, sx, sy, sz, yaw=0.0):
        self._mark()
        P.append_box(self.mesh, unreal.GeometryScriptPrimitiveOptions(), T(x, y, z, yaw),
                     dimension_x=sx, dimension_y=sy, dimension_z=sz, origin=BASE)
        self._apply(mat)
    def cyl(self, mat, x, y, z, r, h, steps=12):
        self._mark()
        P.append_cylinder(self.mesh, unreal.GeometryScriptPrimitiveOptions(), T(x, y, z),
                          radius=r, height=h, radial_steps=steps, origin=BASE)
        self._apply(mat)
    def cone(self, mat, x, y, z, r0, r1, h, steps=12):
        self._mark()
        P.append_cone(self.mesh, unreal.GeometryScriptPrimitiveOptions(), T(x, y, z),
                      base_radius=r0, top_radius=r1, height=h, radial_steps=steps, origin=BASE)
        self._apply(mat)
    def sphere(self, mat, x, y, z, r):
        self._mark()
        P.append_sphere_lat_long(self.mesh, unreal.GeometryScriptPrimitiveOptions(), T(x, y, z),
                                 radius=r, steps_phi=10, steps_theta=14, origin=CENTER)
        self._apply(mat)
    def prism_roof(self, mat, x, y, z, sx, sy, sz):
        """Gable roof (ridge along X) via extruded triangle profile.
        With rotation=[90,0,0]: profile local X -> world Z, local Y -> world Y,
        extrusion (local +Z, `height`) -> world -X. Verified by bbox probe."""
        pts = [unreal.Vector2D(0.0, -sy / 2), unreal.Vector2D(sz, 0.0), unreal.Vector2D(0.0, sy / 2)]
        tf = unreal.Transform(location=[x + sx / 2, y, z], rotation=[90.0, 0.0, 0.0], scale=[1, 1, 1])
        self._mark()
        P.append_simple_extrude_polygon(self.mesh, unreal.GeometryScriptPrimitiveOptions(),
                                        tf, pts, height=sx, capped=True)
        self._apply(mat)
    def save(self, name):
        path = f"{MESH_DIR}/{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            unreal.EditorAssetLibrary.delete_asset(path)
        opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        opts.set_editor_property("enable_recompute_normals", True)
        opts.set_editor_property("enable_recompute_tangents", True)
        opts.set_editor_property("enable_collision", False)
        opts.set_editor_property("enable_nanite", False)
        sm, outcome = NA.create_new_static_mesh_asset_from_mesh(self.mesh, path, opts)
        assert sm, f"failed to create {path}: {outcome}"
        mats = []
        for mn in self.slots:
            entry = unreal.StaticMaterial()
            entry.set_editor_property("material_interface", get_mi(mn))
            entry.set_editor_property("material_slot_name", mn)
            mats.append(entry)
        sm.set_editor_property("static_materials", mats)
        unreal.EditorAssetLibrary.save_asset(path)
        pool.return_mesh(self.mesh)
        print(f"built {path} slots={self.slots}")
        return path

built = []

# probe first: swept polygon support check happens in SM_HouseGable below.

# ---- SM_RoadPlate: 250x250x15 asphalt ----
b = Builder(); b.box("Asphalt", 0, 0, 0, 250, 250, 15); built.append(b.save("SM_RoadPlate"))

# ---- SM_PlotPlate: 2600x2600x20 pavement ----
b = Builder(); b.box("Pavement", 0, 0, 0, 2600, 2600, 20); built.append(b.save("SM_PlotPlate"))

# ---- SM_Tower: glass body + gray roof, 350x350x2000 ----
b = Builder()
b.box("GlassBlue", 0, 0, 0, 350, 350, 2000)
b.box("RoofGray", 0, 0, 2000, 360, 360, 30)
b.box("RoofGray", 100, 80, 2030, 90, 90, 60)   # roof machinery
built.append(b.save("SM_Tower"))

# ---- SM_HouseGable: cream walls + red gable roof ----
b = Builder()
b.box("WallCream", 0, 0, 0, 320, 260, 180)
b.prism_roof("RoofRed", 0, 0, 180, 340, 300, 120)
b.box("WallBrick", 90, 0, 300 - 10, 40, 40, 70)  # chimney
built.append(b.save("SM_HouseGable"))

# ---- SM_HouseFlat: brick walls + parapet ----
b = Builder()
b.box("WallBrick", 0, 0, 0, 300, 300, 240)
b.box("RoofGray", 0, 0, 240, 310, 310, 20)
built.append(b.save("SM_HouseFlat"))

# ---- SM_SchoolL: L-shaped tan building ----
b = Builder()
b.box("SchoolTan", 0, -200, 0, 1500, 500, 380)
b.box("SchoolTan", -500, 250, 0, 500, 900, 380)
b.box("RoofGray", 0, -200, 380, 1520, 520, 25)
b.box("RoofGray", -500, 250, 380, 520, 920, 25)
b.box("MetalDark", 550, -430, 0, 200, 30, 250)   # entrance canopy posts hint
built.append(b.save("SM_SchoolL"))

# ---- SM_HospitalCross: white cross + red helipad hint ----
b = Builder()
b.box("HospWhite", 0, 0, 0, 1300, 450, 700)
b.box("HospWhite", 0, 0, 0, 450, 1300, 700)
b.box("HospWhite", 0, 0, 700, 500, 500, 250)
b.box("HospRed", 0, 0, 950, 220, 220, 8)
built.append(b.save("SM_HospitalCross"))

# ---- SM_TreeRound ----
b = Builder()
b.cyl("TrunkBrown", 0, 0, 0, 14, 170, steps=8)
b.sphere("LeafGreen", 0, 0, 300, 150)
built.append(b.save("SM_TreeRound"))

# ---- SM_TreeConifer ----
b = Builder()
b.cyl("TrunkBrown", 0, 0, 0, 12, 110, steps=8)
b.cone("LeafDark", 0, 0, 100, 135, 2.0, 210, steps=10)
b.cone("LeafDark", 0, 0, 250, 95, 2.0, 170, steps=10)
built.append(b.save("SM_TreeConifer"))

# ---- SM_LampPost: pole + arm + warm head ----
b = Builder()
b.cyl("MetalDark", 0, 0, 0, 12, 25, steps=10)
b.cyl("MetalDark", 0, 0, 25, 5.5, 350, steps=8)
b.box("MetalDark", 40, 0, 368, 80, 7, 7)
b.box("LampWarm", 76, 0, 358, 42, 15, 11)
built.append(b.save("SM_LampPost"))

# ---- SM_Bench ----
b = Builder()
b.box("WoodBench", 0, 0, 40, 140, 45, 6)
b.box("WoodBench", 0, 24, 46, 140, 6, 42)
for lx in (-60, 60):
    for ly in (-16, 16):
        b.box("MetalDark", lx, ly, 0, 8, 8, 40)
built.append(b.save("SM_Bench"))

# ---- SM_Bin ----
b = Builder()
b.cyl("BinGreen", 0, 0, 0, 22, 70, steps=10)
b.cyl("MetalDark", 0, 0, 70, 24, 8, steps=10)
built.append(b.save("SM_Bin"))

# ---- SM_BusShelter ----
b = Builder()
b.box("MetalDark", -140, -50, 0, 12, 12, 230)
b.box("MetalDark", 140, -50, 0, 12, 12, 230)
b.box("ShelterBlue", 0, 0, 230, 320, 140, 12)
b.box("GlassBlue", 0, -55, 20, 300, 6, 200)
b.box("WoodBench", 0, -30, 45, 240, 35, 8)
built.append(b.save("SM_BusShelter"))

print("ALL BUILT:", len(built))
mcp_result = {"built": built}
