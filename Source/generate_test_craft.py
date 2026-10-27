#!/usr/bin/env python3
"""Generate an unrun KSP 1.12.5 static test rig and check its attachment graph.

Only hand-authored craft data is emitted. No original models or sample craft
content is copied. Requires Python 3.8+; no third-party Python packages.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "Tests"
SQRT_HALF = math.sqrt(0.5)
BODY_ROT = (SQRT_HALF, 0.0, 0.0, SQRT_HALF)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def norm(v):
    return math.sqrt(sum(x*x for x in v))


def rotate(q, v):
    x, y, z, w = q
    return (
        (1-2*y*y-2*z*z)*v[0] + (2*x*y-2*z*w)*v[1] + (2*x*z+2*y*w)*v[2],
        (2*x*y+2*z*w)*v[0] + (1-2*x*x-2*z*z)*v[1] + (2*y*z-2*x*w)*v[2],
        (2*x*z-2*y*w)*v[0] + (2*y*z+2*x*w)*v[1] + (1-2*x*x-2*y*y)*v[2],
    )


def multiply(a, b):
    x, y, z, w = a
    X, Y, Z, W = b
    return (w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
            w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z)


def inverse(q):
    return (-q[0], -q[1], -q[2], q[3])


def fmt(v, sep=","):
    return sep.join(f"{0 if abs(x) < 1e-10 else x:.9g}" for x in v)


PARTS = [
    dict(name="Mk33Cockpit", uid=330001, origin=(0, 0, 0), parent=None,
         nodes={"bottom": ((0, -2.70157, 0), (0, -1, 0)), "top": ((0, 2.75384, 0), (0, 1, 0))},
         resources={"LiquidFuel": 7785, "Oxidizer": 9515}),
    dict(name="Mk33MidTank", uid=330002, origin=(0, -7.70157, 0), parent=330001,
         nodes={"top": ((0, 5, 0), (0, 1, 0)),
                "MissionModuleNode1": ((0, 3.75, 1.69861), (0, 0, -1))},
         resources={"LiquidFuel": 18495, "Oxidizer": 22605}),
    dict(name="wbiMk33KrewModule", uid=330003, origin=(0, -3.95157, -0.00207), parent=330002,
         nodes={"mount": ((0, 0, 1.70068), (0, 0, 1)),
                "bottom": ((0, -1.25008, 0), (0, -1, 0))}),
    dict(name="wbiMk33Airlock", uid=330004, origin=(0, -6.45061, -0.00207), parent=330003,
         nodes={"top": ((0, 1.24896, 0), (0, 1, 0))}),
    dict(name="Mk33ProbeCore", uid=330009, origin=(0, 4.33904, 0), parent=330001,
         nodes={"bottom": ((0,-1.5852,0),(0,-1,0)),
                "topNode": ((.0059150452726,1.37194791559,.76936990023),(0,1,0))}),
    dict(name="Mk33DockingNoseCone", uid=330010,
         origin=(.0059150452726,5.71098791559,.76936990023), parent=330009,
         nodes={"bottom01": ((0,0,0),(0,-1,0))}),
]
PAIRS = [
    (330001, "bottom", 330002, "top"),
    (330002, "MissionModuleNode1", 330003, "mount"),
    (330003, "bottom", 330004, "top"),
    (330001, "top", 330009, "bottom"),
    (330009, "topNode", 330010, "bottom01"),
]

# Stock clamps remain upright in world space. Their surface attachment and
# tower extension are illustrative until the craft has been opened in KSP.
for i, (x, z) in enumerate([(-2.7, -4), (2.7, -4), (-2.7, -10), (2.7, -10)]):
    yaw = SQRT_HALF if x < 0 else -SQRT_HALF
    PARTS.append(dict(name="launchClamp1", uid=330005+i, parent=330002,
                      world=(x, 4.5, z), rotation=(0, yaw, 0, SQRT_HALF),
                      nodes={}, surface=True))


def generate():
    TESTS.mkdir(parents=True, exist_ok=True)
    by_id = {p["uid"]: p for p in PARTS}
    for p in PARTS:
        p["rotation"] = p.get("rotation", BODY_ROT)
        if "world" not in p:
            p["world"] = add((0, 5, 0), rotate(BODY_ROT, p["origin"]))
        p["id"] = f'{p["name"]}_{p["uid"]}'
        p["children"] = [q["uid"] for q in PARTS if q["parent"] == p["uid"]]
        p["attachments"] = {}
    checks = []
    for aid, an, bid, bn in PAIRS:
        a, b = by_id[aid], by_id[bid]
        av, ad = a["nodes"][an]
        bv, bd = b["nodes"][bn]
        ap = add(a["world"], rotate(a["rotation"], av))
        bp = add(b["world"], rotate(b["rotation"], bv))
        error = norm(sub(ap, bp))
        direction_error = norm(add(rotate(a["rotation"], ad), rotate(b["rotation"], bd)))
        assert error < 1e-6, (aid, bid, error)
        assert direction_error < 1e-6, (aid, bid, direction_error)
        assert b["parent"] == aid
        a["attachments"][an] = bid
        b["attachments"][bn] = aid
        checks.append(dict(pair=f'{a["name"]}.{an} <-> {b["name"]}.{bn}',
                           separation_m=error, opposing_direction_error=direction_error,
                           world_position=ap, reciprocal=True))
    lines = [
        "ship = Mk33 FreeIVA Static Test", "version = 1.12.5",
        "description = Unrun static FreeIVA test rig. Seat two crew in cockpit. Do not stage the clamps. See Mk33FreeIVA/Tests/instructions.md.",
        "type = SPH", "size = 9,8,20", "steamPublishedFileId = 0", "persistentId = 33330000",
        "rot = 0,0,0,1", "missionFlag = Squad/Flags/default", "vesselType = Ship",
        "OverrideDefault = False,False,False,False", "OverrideActionControl = 0,0,0,0",
        "OverrideAxisControl = 0,0,0,0", "OverrideGroupNames = ,,,",
    ]
    for p in PARTS:
        parent = by_id.get(p["parent"])
        relpos = rotate(inverse(parent["rotation"]), sub(p["world"], parent["world"])) if parent else p["world"]
        relrot = multiply(inverse(parent["rotation"]), p["rotation"]) if parent else p["rotation"]
        clamp = p.get("surface", False)
        lines += ["PART", "{", f'\tpart = {p["id"]}', "\tpartName = Part",
                  f'\tpersistentId = {p["uid"]}', f'\tpos = {fmt(p["world"])}',
                  "\tattPos = 0,0,0", f'\tattPos0 = {fmt(relpos)}',
                  f'\trot = {fmt(p["rotation"])}', "\tattRot = 0,0,0,1", f'\tattRot0 = {fmt(relrot)}',
                  "\tmir = 1,1,1", "\tsymMethod = Mirror", "\tautostrutMode = Off", "\trigidAttachment = False",
                  f'\tistg = {0 if clamp else -1}', "\tresPri = 0", "\tdstg = 0", "\tsidx = -1",
                  "\tsqor = -1", "\tsepI = -1", f'\tattm = {1 if clamp else 0}',
                  "\tsameVesselCollision = False", "\tmodCost = 0", "\tmodMass = 0", "\tmodSize = 0,0,0"]
        for uid in p["children"]:
            lines.append(f'\tlink = {by_id[uid]["id"]}')
        for name, uid in p["attachments"].items():
            v, d = p["nodes"][name]
            vs, ds = fmt(v, "|"), fmt(d, "|")
            lines.append(f'\tattN = {name},{by_id[uid]["id"]}_{vs}_{ds}_{vs}_{ds}')
        if clamp:
            lines.append(f'\tsrfN = srfAttach,{parent["id"]}')
            lines += ["\tMODULE", "\t{", "\t\tname = LaunchClamp", "\t\tisEnabled = True",
                      "\t\tscaleFactor = 1", "\t\theight = 4.5", "\t\tstagingEnabled = True",
                      f'\t\ttowerRot = {fmt(inverse(p["rotation"]))}', "\t}",
                      "\tMODULE", "\t{", "\t\tname = ModuleGenerator", "\t\tisEnabled = True",
                      "\t\tgeneratorIsActive = True", "\t\tthrottle = 1", "\t}"]
        for resource, maximum in p.get("resources", {}).items():
            lines += ["\tRESOURCE", "\t{", f"\t\tname = {resource}", "\t\tamount = 0",
                      f"\t\tmaxAmount = {maximum}", "\t\tflowState = True", "\t\tisTweakable = True", "\t}"]
        lines += ["\tEVENTS", "\t{", "\t}", "\tACTIONS", "\t{", "\t}", "\tPARTDATA", "\t{", "\t}", "}"]
    content = "\n".join(lines) + "\n"
    assert content.count("{") == content.count("}")
    assert len(by_id) == len(PARTS) == 10
    # Every nonroot part must be reachable once through the child graph.
    seen = set()
    def visit(uid):
        assert uid not in seen, "cycle or duplicate child"
        seen.add(uid)
        for child in by_id[uid]["children"]:
            assert by_id[child]["parent"] == uid
            visit(child)
    visit(330001)
    assert seen == set(by_id)
    craft = TESTS / "Mk33_FreeIVA_Test.craft"
    craft.write_text(content, encoding="utf-8")
    report = dict(status="STATIC_CHECKS_ONLY_NOT_RUN_IN_KSP", part_count=10,
                  reciprocal_stack_connections=checks, tree_connected_and_acyclic=True,
                  fuel_saved_empty=True, fuel_maxima_unchanged=True,
                  clamps="Placement/tower extension are unverified in KSP; reattach in SPH if necessary.",
                  scope="Attachment graph and coordinates, not FreeIVA/Unity physical passage.",
                  core_part_origins={p["name"]: p["origin"] for p in PARTS if "origin" in p})
    (TESTS / "topology-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {craft.name}: 10 parts; 5 reciprocal node pairs within 1e-6 m; KSP run NOT PERFORMED.")


if __name__ == "__main__":
    generate()
