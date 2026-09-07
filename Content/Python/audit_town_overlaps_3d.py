"""Final 3D-aware overlap audit.
Whitelist (by design):
  - Road x Road: plates tile edge-to-edge
  - CivicPlot x School/Hospital: buildings stand ON their plots
For tree-vs-anything, test the TRUNK footprint (r=20) at ground level, and the
CROWN only against objects taller than crown-bottom (z >= 100*scale).
Everything else: plain AABB with 15% tolerance.
"""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
town = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("PCGVolume", "TownActor"))
comps = town.get_components_by_class(unreal.InstancedStaticMeshComponent)

mesh_dims = {}
def dims(name):
    if name not in mesh_dims:
        sm = unreal.EditorAssetLibrary.load_asset(f"/Game/Town/Meshes/{name}")
        bb = sm.get_bounding_box()
        mesh_dims[name] = ((bb.max.x - bb.min.x) / 2, (bb.max.y - bb.min.y) / 2, bb.max.z - bb.min.z)
    return mesh_dims[name]

TREES = {"SM_TreeRound", "SM_TreeConifer"}
items = []
for c in comps:
    sm = c.get_editor_property("static_mesh")
    if not sm:
        continue
    name = sm.get_name()
    bhx, bhy, bz = dims(name)
    for i in range(c.get_instance_count()):
        tf = c.get_instance_transform(i, True)
        loc, sc, rot = tf.translation, tf.scale3d, tf.rotation.rotator()
        hx, hy = bhx * sc.x, bhy * sc.y
        yaw = abs(rot.yaw) % 90.0
        if 10.0 < yaw < 80.0:
            hx = hy = max(hx, hy)
        is_tree = name in TREES
        trunk_r = 20.0 * sc.x if is_tree else None
        height = bz * sc.z
        items.append((name, loc.x, loc.y, hx, hy, is_tree, trunk_r, height))

print("instances:", len(items))

CELL = 800.0
grid = {}
for idx, it in enumerate(items):
    _, x, y, hx, hy = it[0], it[1], it[2], it[3], it[4]
    for gx in range(int((x - hx) // CELL), int((x + hx) // CELL) + 1):
        for gy in range(int((y - hy) // CELL), int((y + hy) // CELL) + 1):
            grid.setdefault((gx, gy), []).append(idx)

PLOT = {"SM_PlotPlate"}
CIVIC = {"SM_SchoolL", "SM_HospitalCross"}
LOW = {"SM_RoadPlate", "SM_PlotPlate"}   # z <= 25: crowns overhang freely

def footprint(it, vs_low):
    """(hx, hy) to use: trees use trunk vs low/ground objects, crown otherwise."""
    name, x, y, hx, hy, is_tree, trunk_r, h = it
    if is_tree and vs_low:
        return trunk_r, trunk_r
    return hx, hy

pair_counts, examples, seen = {}, {}, set()
for cell, idxs in grid.items():
    for i in range(len(idxs)):
        for j in range(i + 1, len(idxs)):
            a, b = idxs[i], idxs[j]
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            seen.add(key)
            ia, ib = items[a], items[b]
            na, nb = ia[0], ib[0]
            if na == "SM_RoadPlate" and nb == "SM_RoadPlate":
                continue
            if (na in PLOT and nb in CIVIC) or (nb in PLOT and na in CIVIC):
                continue
            low_a, low_b = na in LOW, nb in LOW
            ahx, ahy = footprint(ia, vs_low=low_b)
            bhx, bhy = footprint(ib, vs_low=low_a)
            if abs(ia[1] - ib[1]) < (ahx + bhx) * 0.85 and abs(ia[2] - ib[2]) < (ahy + bhy) * 0.85:
                pk = tuple(sorted((na, nb)))
                pair_counts[pk] = pair_counts.get(pk, 0) + 1
                if pk not in examples:
                    examples[pk] = (ia, ib)

print("\n=== REAL conflicts (3D-aware, whitelist applied) ===")
for pk, n in sorted(pair_counts.items(), key=lambda kv: -kv[1]):
    ia, ib = examples[pk]
    print(f"  {pk[0]} x {pk[1]}: {n}   e.g. ({ia[1]:.0f},{ia[2]:.0f}) vs ({ib[1]:.0f},{ib[2]:.0f})")
if not pair_counts:
    print("  NONE - town is clean")
mcp_result = {"instances": len(items),
              "conflicts": {f"{k[0]}|{k[1]}": v for k, v in pair_counts.items()}}
