"""Audit the town for overlaps, from the generated output (ground truth).

For every tagged branch, collect world-space 2D footprints:
  center (x,y) + half-extents from actual spawned meshes (mesh bounds * point
  scale) in mesh mode.
Then check:
  1. intra-category: min pairwise center distance vs combined footprints
  2. inter-category: pairwise category overlap counts (AABB test)
Report worst offenders with concrete examples.
"""
import unreal

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
town = next(a for a in eas.get_all_level_actors() if a.get_class().get_name() == "TownActor")
pcg = town.get_editor_property("pcg_component")
out = pcg.get_generated_graph_output()

# mesh half-extent lookup (XY) from asset bounds
mesh_he = {}
def half_extents_for(mesh_name):
    if mesh_name not in mesh_he:
        sm = unreal.EditorAssetLibrary.load_asset(f"/Game/Town/Meshes/{mesh_name}")
        bb = sm.get_bounding_box()
        mesh_he[mesh_name] = ((bb.max.x - bb.min.x) / 2.0, (bb.max.y - bb.min.y) / 2.0)
    return mesh_he[mesh_name]

# Collect instances per category from ISM components (mesh mode ground truth)
comps = town.get_components_by_class(unreal.InstancedStaticMeshComponent)
items = []   # (category_guess_by_mesh, mesh_name, x, y, hx, hy)
MESH2CAT = {
    "SM_RoadPlate": "Road", "SM_PlotPlate": "CivicPlot", "SM_SchoolL": "School",
    "SM_HospitalCross": "Hospital", "SM_Tower": "Commercial",
    "SM_HouseGable": "House", "SM_HouseFlat": "House",
    "SM_TreeRound": "Tree/StreetTree", "SM_TreeConifer": "Tree/StreetTree",
    "SM_LampPost": "Light", "SM_Bench": "Bench", "SM_Bin": "Bin",
    "SM_BusShelter": "BusStop",
}
for c in comps:
    sm = c.get_editor_property("static_mesh")
    if not sm:
        continue
    name = sm.get_name()
    cat = MESH2CAT.get(name, name)
    bhx, bhy = half_extents_for(name)
    for i in range(c.get_instance_count()):
        tf = c.get_instance_transform(i, True)
        loc = tf.translation
        scale = tf.scale3d
        # yaw-rotated AABB approximation: use max(|hx|,|hy|) when rotated
        rot = tf.rotation.rotator()
        yaw = abs(rot.yaw) % 90.0
        hx, hy = bhx * scale.x, bhy * scale.y
        if 10.0 < yaw < 80.0:
            m = max(hx, hy)
            hx = hy = m
        items.append((cat, name, loc.x, loc.y, hx, hy))

print(f"instances collected: {len(items)}")

# spatial hash for pair queries
CELL = 800.0
grid = {}
for idx, it in enumerate(items):
    _, _, x, y, hx, hy = it
    for gx in range(int((x - hx) // CELL), int((x + hx) // CELL) + 1):
        for gy in range(int((y - hy) // CELL), int((y + hy) // CELL) + 1):
            grid.setdefault((gx, gy), []).append(idx)

def aabb_overlap(a, b, shrink=1.0):
    _, _, ax, ay, ahx, ahy = a
    _, _, bx, by, bhx2, bhy2 = b
    return (abs(ax - bx) < (ahx + bhx2) * shrink) and (abs(ay - by) < (ahy + bhy2) * shrink)

# count overlaps per category pair (shrink=0.85 to ignore mere edge kisses)
pair_counts = {}
examples = {}
seen = set()
for cell, idxs in grid.items():
    for i in range(len(idxs)):
        for j in range(i + 1, len(idxs)):
            a, b = idxs[i], idxs[j]
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            seen.add(key)
            ia, ib = items[a], items[b]
            # roads tile edge-to-edge by design; skip road-road
            if ia[0] == "Road" and ib[0] == "Road":
                continue
            if aabb_overlap(ia, ib, shrink=0.85):
                pk = tuple(sorted((ia[0], ib[0])))
                pair_counts[pk] = pair_counts.get(pk, 0) + 1
                if pk not in examples:
                    examples[pk] = (ia, ib)

print("\n=== overlap pairs (AABB, 15% tolerance, road-road excluded) ===")
for pk, n in sorted(pair_counts.items(), key=lambda kv: -kv[1]):
    print(f"  {pk[0]} x {pk[1]}: {n}")
    ia, ib = examples[pk]
    print(f"     e.g. {ia[1]}@({ia[2]:.0f},{ia[3]:.0f}) he=({ia[4]:.0f},{ia[5]:.0f})"
          f"  vs {ib[1]}@({ib[2]:.0f},{ib[3]:.0f}) he=({ib[4]:.0f},{ib[5]:.0f})")
if not pair_counts:
    print("  none")

mcp_result = {"instances": len(items),
              "overlaps": {f"{k[0]}|{k[1]}": v for k, v in pair_counts.items()}}
