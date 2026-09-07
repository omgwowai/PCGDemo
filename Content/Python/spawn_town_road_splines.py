"""Spawn demo road-spline actors (tag: TownRoad) for the spline road source.
Creates a few curved roads through town. Each actor: plain Actor + SplineComponent.
mcp_args: {"clear_only": false}
"""
import unreal, math

args = globals().get("mcp_args") or {}
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)

# remove existing TownRoad actors first (idempotent)
removed = 0
for a in list(eas.get_all_level_actors()):
    if a.actor_has_tag("TownRoad"):
        eas.destroy_actor(a)
        removed += 1
print("removed old TownRoad actors:", removed)
if args.get("clear_only"):
    mcp_result = {"removed": removed, "created": 0}
else:
    ROADS = [
        # S-curve main street, west-east
        [(-11000, -6000), (-5000, -2000), (2000, -3500), (8000, 1000), (11000, 2500)],
        # north-south avenue with a bow
        [(-2000, -11000), (-3500, -4000), (-1500, 3000), (-2500, 11000)],
        # ring-ish arc in the NE quadrant
        [(2000, 9000), (6000, 7500), (9000, 4500), (10000, 500)],
    ]
    created = []
    for i, pts in enumerate(ROADS):
        actor = eas.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
        actor.set_actor_label(f"TownRoadSpline_{i}")
        handles = sds.k2_gather_subobject_data_for_instance(actor)
        params = unreal.AddNewSubobjectParams()
        params.set_editor_property("parent_handle", handles[0])
        params.set_editor_property("new_class", unreal.SplineComponent)
        sds.add_new_subobject(params)
        sp = actor.get_components_by_class(unreal.SplineComponent)[0]
        sp.clear_spline_points(True)
        for x, y in pts:
            sp.add_spline_point(unreal.Vector(x, y, 0.0), unreal.SplineCoordinateSpace.WORLD, False)
        sp.update_spline()
        actor.set_editor_property("tags", ["TownRoad"])
        created.append(str(actor.get_actor_label()))
        print(f"created {actor.get_actor_label()}: {len(pts)} pts, len={sp.get_spline_length():.0f}")
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.save_current_level()
    mcp_result = {"removed": removed, "created": len(created), "actors": created}
