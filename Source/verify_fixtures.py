"""Inspect actual exported decorative mounting and capsule clearance.

Python 3 + NumPy + SciPy and bundled .mu reader. Optional --baseline compares
all physical colliders and transforms with an earlier package. This is exported
geometry validation, not Unity mesh cooking, rendering, or a gameplay test.
SPDX-License-Identifier: GPL-2.0-or-later.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'Source' / 'source_checks'))
from inspect_mu import nodes

# Import just the reusable exact distance functions, without running the other
# script's main report generation or changing any of its retained results.
tree = ast.parse((ROOT / 'Source' / 'validate_corridors.py').read_text())
function_names = {'point_triangle', 'segment_segment', 'segment_triangle', 'sample_segments', 'test_path'}
tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in function_names]
scope = {'np': np}
exec(compile(tree, 'capsule-distance-functions', 'exec'), scope)
point_triangle = scope['point_triangle']
segment_triangle = scope['segment_triangle']


def mesh_world(item, mesh):
    matrix = item['matrix']
    vertices = (np.array(mesh.verts) @ matrix[:3, :3].T + matrix[:3, 3])[:, [0, 2, 1]]
    faces = np.array(sum(mesh.submeshes, []))[:, [0, 2, 1]]
    return vertices, faces, vertices[faces]


def decode(root, name):
    rendered, solid, signatures = {}, {}, {}
    for item in nodes(root / 'Models' / (name + '.mu')):
        obj = item['object']
        if hasattr(obj, 'renderer') and hasattr(obj, 'shared_mesh'):
            rendered[item['name']] = mesh_world(item, obj.shared_mesh)[2]
        collider = getattr(obj, 'collider', None)
        if collider is None:
            continue
        data = {'type': type(collider).__name__, 'layer': obj.tag_and_layer.layer,
                'tag': obj.tag_and_layer.tag, 'matrix': item['matrix'].tolist()}
        for field in ('isTrigger', 'convex', 'center', 'size', 'radius', 'height', 'direction'):
            if hasattr(collider, field):
                data[field] = getattr(collider, field)
        if hasattr(collider, 'mesh'):
            data['vertices'] = collider.mesh.verts
            data['submeshes'] = collider.mesh.submeshes
            if not collider.isTrigger:
                solid[item['name']] = mesh_world(item, collider.mesh)[2]
        signatures[item['name']] = data
    return rendered, solid, signatures


def normals(triangles):
    result = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    length = np.linalg.norm(result, axis=1)
    assert (length > 1e-12).all(), 'degenerate mounting triangles'
    return result / length[:, None]


SAMPLE_BARYCENTRIC = np.array([(1, 0, 0), (0, 1, 0), (0, 0, 1),
                               (.5, .5, 0), (.5, 0, .5), (0, .5, .5),
                               (1/3, 1/3, 1/3)])


def mounting_backfaces(housing, skin):
    """Identify outward mounting faces using the independent shell normals.

    Fixture fronts face into the room. Their mounting backs face oppositely to
    the nearest inward shell triangle. Vertices, edge midpoints, and centroids
    of those back faces must be close to the actual skin, not a nominal radius.
    """
    skin_normals = normals(skin)
    fixture_normals = normals(housing)
    back = []
    distances = []
    for index, triangle in enumerate(housing):
        center = triangle.mean(0)
        ds = point_triangle(center, skin)
        nearest = int(np.argmin(ds))
        if np.dot(fixture_normals[index], skin_normals[nearest]) < -.70:
            back.append(index)
            for sample in SAMPLE_BARYCENTRIC @ triangle:
                distances.append(float(np.sqrt(point_triangle(sample, skin).min())))
    return {'mounting_back_triangles': len(back), 'sampled_back_points': len(distances),
            'minimum_gap_metres': min(distances) if distances else None,
            'maximum_gap_metres': max(distances) if distances else None,
            'attached': bool(distances) and max(distances) <= .0021}


def mesh_distance(a, b, stop_at=None):
    best = float('inf')
    # Segment/triangle tests in both directions also cover triangle crossings,
    # coplanar overlap, parallel faces, and a small face inside a larger face.
    for source, target in ((a, b), (b, a)):
        for tri in source:
            delta = np.maximum(target.min(1) - tri.max(0), 0) + np.maximum(tri.min(0) - target.max(1), 0)
            candidates = target[(delta * delta).sum(1) <= best * best]
            if not len(candidates):
                continue
            for i, j in ((0, 1), (1, 2), (2, 0)):
                best = min(best, float(np.sqrt(segment_triangle(tri[i], tri[j], candidates).min())))
                if stop_at is not None and best <= stop_at:
                    return best
    return best


def contact_graph(rendered, skin):
    parts = {name: tri for name, tri in rendered.items()
             if 'Access' in name and any(word in name for word in ('Rung', 'Rail', 'Stile', 'Foot', 'Mount'))}
    assert parts, 'no visible ladder assembly found'
    graph = {name: [] for name in parts}
    graph['shell'] = []
    for name, triangles in parts.items():
        if mesh_distance(triangles, skin, stop_at=.0021) <= .0021:
            graph[name].append('shell'); graph['shell'].append(name)
    names = list(parts)
    for i, name in enumerate(names):
        for other in names[i+1:]:
            if mesh_distance(parts[name], parts[other], stop_at=.0021) <= .0021:
                graph[name].append(other); graph[other].append(name)
    reached, pending = {'shell'}, ['shell']
    while pending:
        current = pending.pop()
        for other in graph[current]:
            if other not in reached:
                reached.add(other); pending.append(other)
    unsupported = sorted(set(parts) - reached)
    assert not unsupported, ('disconnected visible ladder pieces', unsupported)
    rails = {name for name in parts if 'Rail' in name or 'Stile' in name}
    rung_supports = {}
    for name in parts:
        if 'Rung' in name:
            connected = sorted(rails.intersection(graph[name]))
            assert len(connected) >= 2, ('rung lacks both side supports', name, connected)
            rung_supports[name] = connected
    return {'contact_tolerance_metres': .0021, 'contacts': graph,
            'all_visible_pieces_reach_shell_through_real_triangle_contacts': True,
            'each_rung_contacts_both_side_rails': rung_supports}


def capsule_clearance(rendered, solid, path, label):
    decorative = [tri for name, tri in rendered.items() if 'Surface' not in name]
    triangles = np.concatenate(list(solid.values()) + decorative)
    low, high = np.min(path, axis=0) - .40, np.max(path, axis=0) + .40
    triangles = triangles[((triangles.max(1) >= low) & (triangles.min(1) <= high)).all(1)]
    checks = {shape: scope['test_path'](triangles, path, helmet)
              for shape, helmet in [('body', False), ('helmet', True)]}
    assert all(result['clear'] for result in checks.values()), (label, checks)
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, help='Earlier Mk33FreeIVA folder for physics invariance and gap evidence')
    args = parser.parse_args()
    all_models = {p.stem: decode(ROOT, p.stem) for p in sorted((ROOT / 'Models').glob('*.mu'))}
    report = {'in_game_tested': False,
              'method': 'Decode shipped .mu triangles; sample fixture back faces against actual pressure skin; compute ladder contact graph and swept capsule clearance including render-only hardware.',
              'fixtures': {}, 'clearance': {}}

    for model in ('CockpitCorridor', 'KrewDockPassage', 'KrewDockTube', 'ProbeCorePassage', 'NoseDockPassage'):
        rendered, solid, signatures = all_models[model]
        skin = np.concatenate([tri for name, tri in solid.items() if 'CentralSeal' not in name])
        housings = {name: triangles for name, triangles in rendered.items() if name.lower().endswith('housing')}
        assert housings, ('fixture housing absent', model)
        for name, triangles in housings.items():
            check = mounting_backfaces(triangles, skin)
            assert check['attached'], ('housing rear not attached to actual skin', model, name, check)
            contact = mesh_distance(triangles, skin, stop_at=.00001)
            assert contact <= .00001, ('housing is near skin but does not intersect/touch it', model, name, contact)
            check['mesh_contact_distance_metres'] = contact
            check['housing_mesh_intersects_or_touches_skin'] = True
            report['fixtures'][model + '/' + name] = check
        # A diffuser must touch its metal housing. A light volume has no mesh
        # and is intentionally excluded from this visible-object test.
        for name, triangles in rendered.items():
            if not name.lower().endswith(('lens', 'diffuser')):
                continue
            stem = name.rsplit('_', 1)[0] if '_' in name else name[:-4]
            candidates = [tri for other, tri in housings.items() if other.startswith(stem)]
            assert candidates, ('diffuser housing not found', model, name)
            gap = min(mesh_distance(triangles, tri, stop_at=.0021) for tri in candidates)
            assert gap <= .0021, ('floating diffuser', model, name, gap)
            report['fixtures'][model + '/' + name] = {'contact_with_housing_gap_metres': gap}

    cockpit = all_models['CockpitCorridor']
    report['ladder'] = contact_graph(cockpit[0], np.concatenate(list(cockpit[1].values())))
    geometry = json.loads((ROOT / 'Tests' / 'corridor-geometry.json').read_text())['models']
    c, t = (np.array(p) for p in geometry['CockpitCorridor']['ports'][:2])
    junction = c + (t-c) * ((.525-c[2])/(t[2]-c[2]))
    report['clearance']['cockpit_main'] = capsule_clearance(*cockpit[:2], [c, t], 'cockpit_main')
    report['clearance']['cockpit_shaft'] = capsule_clearance(*cockpit[:2], [(0,1.49,-.04404),(0,1.49,.525),junction.tolist()], 'cockpit_shaft')
    krew_render = dict(all_models['KrewDockPassage'][0], **all_models['KrewDockTube'][0])
    krew_solid = dict(all_models['KrewDockPassage'][1], **all_models['KrewDockTube'][1])
    route = geometry['KrewDockPassage']['route'][:-1] + [(0,geometry['KrewDockPassage']['outlet_y']+1.0,.61551148)]
    report['clearance']['krew_transfer'] = capsule_clearance(krew_render, krew_solid, route, 'krew_transfer')
    nose = json.loads((ROOT / 'Tests' / 'nose-passage-geometry.json').read_text())['models']
    report['clearance']['probe_passage'] = capsule_clearance(*all_models['ProbeCorePassage'][:2], nose['ProbeCorePassage']['ports'], 'probe_passage')
    report['clearance']['nose_passage'] = capsule_clearance(*all_models['NoseDockPassage'][:2], [nose['NoseDockPassage']['ports'][0],(0,0,-1.245)], 'nose_passage')

    if args.baseline:
        invariants = {}
        for model, (rendered, solid, signatures) in all_models.items():
            old = decode(args.baseline, model)[2]
            assert old == signatures, ('physical collider data or transform changed', model)
            serialized = json.dumps(signatures, sort_keys=True).encode()
            invariants[model] = {'all_colliders_and_world_transforms_unchanged': True,
                                 'collider_count': len(signatures),
                                 'canonical_sha256': hashlib.sha256(serialized).hexdigest()}
        report['physical_invariance'] = invariants
        baseline_gaps = {}
        for model in ('CockpitCorridor', 'KrewDockPassage', 'KrewDockTube', 'ProbeCorePassage'):
            rendered, solid, unused = decode(args.baseline, model)
            skin = np.concatenate([tri for name, tri in solid.items() if 'CentralSeal' not in name])
            for name, triangles in rendered.items():
                if 'Fixture' in name:
                    check = mounting_backfaces(triangles, skin)
                    baseline_gaps[model + '/' + name] = check
        report['baseline_fixture_gaps'] = baseline_gaps
    destination = ROOT / 'Tests' / 'fixture-mounting-checks.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
