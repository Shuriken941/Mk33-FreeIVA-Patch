"""Independent Mk-33 nose route/source aperture verification.

Python 3 + NumPy + SciPy; uses bundled GPL mu and convex-cut research helpers.
Supply --assets pointing at the original Mk-33 Parts/SharedAssets directory.
This script does not execute KSP, ModuleManager, Unity or native MeshCutter.
SPDX-License-Identifier: GPL-2.0-or-later.
"""
import argparse
import ast
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'Source' / 'source_checks'))
from cut_math import nodes, distances, cut, cylinder_planes
from verify_package import parse, value

PART_TO_INTERNAL = np.array([[-1., 0., 0.], [0., 0., -1.], [0., -1., 0.]])


def modules(node, name):
    return [child for child in node['nodes'] if child['type'] == 'MODULE' and value(child, 'name') == name]


def triple(text):
    return np.array([float(item) for item in text.split(',')])


def verify_configuration():
    roots = parse((ROOT / 'Patches' / 'Mk33_FreeIVA.cfg').read_text())
    interiors = {}
    for node in roots:
        assert 'NEEDS[Mk33FreeIVA,FreeIva,' in node['type'], ('patch lacks own DLL prerequisite', node['type'])
        if node['type'].startswith('@INTERNAL['):
            interiors[node['type'].split('[', 1)[1].split(']', 1)[0]] = node
        elif node['type'].startswith('INTERNAL:'):
            interiors[value(node, 'name')] = node
    assert set(interiors) == {'wbiMk33CockpitSpace', 'wbiMk33CrewModuleSpace', 'wbiMk33AirlockSpace',
                              'wbiMk33ControlCabSpace', 'Mk33FreeIVA_ProbeCoreSpace', 'Mk33FreeIVA_NoseDockSpace'}
    seals = {}
    for name, node in interiors.items():
        native = modules(node, 'InternalModuleFreeIva')
        assert len(native) == 1, name
        pressure = modules(node, 'Mk33FreeIvaPressureHatch')
        ids = [value(hatch, 'hatchId') for hatch in pressure]
        assert all(ids) and len(ids) == len(set(ids)), name
        assert not set(ids).intersection(seals), 'pressure IDs must be globally unambiguous'
        seals.update(zip(ids, pressure))
        assert all(node['nodes'].index(hatch) < node['nodes'].index(native[0]) for hatch in pressure), name
        geometry = modules(node, 'Mk33FreeIvaGeometry')
        authored = modules(node, 'Mk33FreeIvaAuthoredShell')
        assert len(geometry) + len(authored) == 1, name
        if geometry:
            required = [v for key, v in geometry[0]['values'] if key == 'requiredHatchId']
            assert sorted(required) == sorted(ids), (name, 'source cut seal prerequisites', required, ids)
            assert all(node['nodes'].index(hatch) < node['nodes'].index(geometry[0]) for hatch in pressure), name
            assert node['nodes'].index(geometry[0]) < node['nodes'].index(native[0]), name
            required_original = [v for key, v in geometry[0]['values'] if key == 'requiredOriginalDoor']
            original = modules(node, 'Mk33FreeIvaHatch')
            assert sorted(required_original) == sorted(value(h, 'doorTransformName') for h in original), name
            assert all(node['nodes'].index(h) < node['nodes'].index(geometry[0]) for h in original), name
            extras = [v for key, v in native[0]['values'] if key == 'shellColliderName' and v != 'Mk33Shell']
            required_shells = [v for key, v in geometry[0]['values'] if key == 'requiredShell']
            assert sorted(extras) == sorted(required_shells), (name, extras, required_shells)
        if authored:
            assert all(node['nodes'].index(authored[0]) < node['nodes'].index(hatch) for hatch in pressure), name
        for mask in modules(node, 'Mk33FreeIvaWindowMask'):
            assert node['nodes'].index(mask) < node['nodes'].index(native[0]), name
        assert not any(child['type'] == 'PROP' and value(child, 'name', '').startswith('Mk33FreeIVA_')
                       for child in node['nodes']), 'pressure caps still depend on PROP lookup'
        available = {}
        for model in (child for child in node['nodes'] if child['type'] == 'MODEL'):
            path = ROOT.parent / (value(model, 'model') + '.mu')
            assert path.is_file(), path
            for item in nodes(path):
                if hasattr(item['object'], 'collider'):
                    available[item['name']] = item['object'].collider
        expected = [v for key, v in native[0]['values'] if key == 'shellColliderName' and v != 'Mk33Shell']
        if authored:
            expected += [v for key, v in authored[0]['values'] if key == 'sourceTransform']
        for collider_name in expected:
            assert collider_name in available, (name, 'missing authored shell collider', collider_name)
            collider = available[collider_name]
            assert hasattr(collider, 'mesh') and not collider.isTrigger and not collider.convex, collider_name
    assert value(seals['CockpitNose'], 'attachNodeId') == 'top'
    assert value(seals['ProbeRear'], 'attachNodeId') == 'bottom'
    assert value(seals['ProbeFront'], 'attachNodeId') == 'topNode'
    assert value(seals['NoseRear'], 'attachNodeId') == 'bottom01'
    assert value(seals['NoseDock'], 'dockingPortNodeName') == 'dockingNode'
    assert value(seals['NoseDock'], 'requireDeploy') == 'true'
    assert value(seals['NoseDock'], 'tubeTransformName') == 'Mk33NoseDockTube'
    assert value(seals['CockpitAftExit'], 'requireConnected') == 'true'
    assert value(seals['CockpitAftEntry'], 'requireConnected') == 'false'
    assert all(value(hatch, 'requireConnected') == 'true' for key, hatch in seals.items() if key != 'CockpitAftEntry')
    for part in ('Mk33ProbeCore', 'Mk33DockingNoseCone'):
        node = next(n for n in roots if n['type'].startswith('@PART[' + part + ']'))
        settings = next(n for n in node['nodes'] if n['type'] == '%MODULE[ModuleFreeIva]')
        assert value(settings, '%forceInternalCreation') == 'true'
        assert value(settings, '%allowsUnbuckling') == 'false'
    node = next(n for n in roots if n['type'].startswith('@PART[Mk33DockingNoseCone]'))
    assert value(next(n for n in node['nodes'] if n['type'] == '%MODULE[ModuleFreeIva]'), '%deployAnimationName') == 'Deploy'
    return interiors, {'six_internal_configurations': True, 'generated_pressure_caps': len(seals),
                       'source_cut_caps_loaded_and_required_before_cuts': True,
                       'original_doors_and_auxiliary_shells_required_before_cuts': True,
                       'authored_shell_validated_before_pressure_caps': True,
                       'all_walking_patches_require_own_dll': True,
                       'nose_route_native_node_bindings': True,
                       'only_closed_local_corridor_entrance_can_open_without_peer': True}


def authored_triangles(model_name, tube_scale=None):
    result = []
    for item in nodes(ROOT / 'Models' / (model_name + '.mu')):
        collider = getattr(item['object'], 'collider', None)
        if collider is None or not hasattr(collider, 'mesh') or collider.isTrigger:
            continue
        matrix = item['matrix']
        vertices = (np.array(collider.mesh.verts) @ matrix[:3, :3].T + matrix[:3, 3])[:, [0, 2, 1]]
        if tube_scale is not None:
            assert item['name'] == 'Mk33KrewDockTube'
            vertices[:, 1] = 1.80 + (vertices[:, 1] - 1.80) * tube_scale
        faces = np.array(sum(collider.mesh.submeshes, []))[:, [0, 2, 1]]
        result.extend(vertices[faces])
    return np.array(result)


def krew_source_and_authored_clearance(assets, interiors):
    """Check the open original door route against BOTH source and new shells."""
    module = modules(interiors['wbiMk33CrewModuleSpace'], 'Mk33FreeIvaGeometry')[0]
    sources = {v for key, v in module['values'] if key == 'sourceTransform'}
    tools = {}
    for tool in (n for n in module['nodes'] if n['type'] == 'Cut'):
        position = triple(value(tool, 'position'))
        rotation=triple(value(tool,'rotation'))
        if value(tool, 'type') == 'ProceduralCylinder':
            planes = cylinder_planes(0, 0, 0, float(value(tool, 'height')),
                                     r=float(value(tool, 'radius')))
            if np.allclose(rotation,[-90,0,0]):
                turn=np.array([[1.,0.,0.],[0.,0.,1.],[0.,-1.,0.]])
            else:
                assert np.allclose(rotation,0), ('unsupported independent cylinder rotation',rotation)
                turn=np.eye(3)
            planes=[(turn@n,d+np.dot(turn@n,position)) for n,d in planes]
        else:
            assert value(tool, 'type') == 'Cube' and np.allclose(rotation,0)
            size = triple(value(tool, 'scale'))
            planes = []
            for axis in range(3):
                normal = np.eye(3)[axis]
                planes.extend([(normal, position[axis] + size[axis] / 2),
                               (-normal, -position[axis] + size[axis] / 2)])
        tools.setdefault(value(tool, 'target'), []).append(planes)
    original = []
    for item in nodes(assets / 'crewModuleIVA.mu'):
        if 'mesh' not in item or item['name'] not in sources:
            continue
        tris = item['verts'][np.array(sum(item['mesh'].submeshes, []))]
        for planes in tools.get(item['name'], []):
            tris = cut(tris, planes)
        original.extend(tris)
    source = np.array(original)
    passage = authored_triangles('KrewDockPassage')
    sleeve = authored_triangles('KrewDockTube', 2.8598599433898926 - 1.80)
    triangles = np.concatenate([source, passage, sleeve])
    geometry = json.loads((ROOT / 'Tests' / 'corridor-geometry.json').read_text())['models']['KrewDockPassage']
    route = geometry['route'][:-1] + [[0, 2.8598599433898926, .61551148]]
    # Isolate the reusable exact distance/path functions without importing the
    # old script's report-writing/main block or executing unrelated tests.
    tree = ast.parse((ROOT / 'Source' / 'validate_corridors.py').read_text())
    function_names = {'point_triangle', 'segment_segment', 'segment_triangle', 'sample_segments', 'test_path'}
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in function_names]
    scope = {'np': np}
    exec(compile(tree, 'validate_corridors-functions', 'exec'), scope)
    # Faces wholly beyond this route's expanded box cannot approach either
    # capsule. Culling only accelerates the independent distance calculation.
    low, high = np.min(route, axis=0) - .40, np.max(route, axis=0) + .40
    keep = ((triangles.max(1) >= low) & (triangles.min(1) <= high)).all(1)
    triangles = triangles[keep]
    checks = {}
    for direction, path in [('outward', route), ('inward', route[::-1])]:
        checks[direction] = {}
        for label, helmet in [('body', False), ('helmet', True)]:
            result = scope['test_path'](triangles, path, helmet)
            assert result['clear'], (direction, label, result)
            checks[direction][label] = result
    return {'source_meshes_after_configured_cuts_included': True,
            'actual_central_door_shaft_and_deployed_sleeve_colliders_included': True,
            'embedded_central_door_assumed_open': True,
            'neighboring_exterior_crewDoor_not_used': True,
            'tested_triangles': len(triangles), 'paths': checks,
            'limitations': 'Independent source cut math and actual authored triangles, not native MeshCutter, Unity collider cooking or gameplay.'}


def point_from_model(path, name):
    item = next(n for n in nodes(path) if n['name'] == name)
    return item['matrix'][:3, 3][[0, 2, 1]]


def inspect_front_cap(assets, do_cut):
    triangles, names = [], []
    planes = cylinder_planes(0, -.6253, -2.84, -2.64, r=.525)
    for item in nodes(assets / 'cockpitIVA.mu'):
        if 'mesh' not in item or item['name'] in ('crewDoor', 'seatbelts'):
            continue
        mesh = item['verts'][np.array(sum(item['mesh'].submeshes, []))]
        if do_cut and item['name'] in ('crewTube', 'Dashboard'):
            mesh = cut(mesh, planes)
        triangles.extend(mesh)
        names.extend([item['name']] * len(mesh))
    triangles, names = np.array(triangles), np.array(names)
    low, high = triangles.min(1), triangles.max(1)
    results = {}
    for label, radius in [('body', .20), ('helmet', .225)]:
        best, nearest, worst = float('inf'), None, None
        for z in np.linspace(-2.95, -2.3, 131):
            center = [0, -.6253, float(z)]
            for dy in np.linspace(-(.30 - radius), .30 - radius, 41):
                point = np.array(center) + [0, dy, 0]
                delta = np.maximum(low - point, 0) + np.maximum(point - high, 0)
                ids = np.flatnonzero((delta * delta).sum(1) < .65 ** 2)
                if not len(ids):
                    continue
                ds = distances(point, triangles[ids])
                j = int(np.argmin(ds))
                clearance = float(ds[j]) - radius - .01
                if clearance < best:
                    best, nearest, worst = clearance, str(names[ids[j]]), center
        results[label] = {'radius_metres': radius, 'height_metres': .60,
                          'conservative_clearance_lower_bound_metres': best,
                          'nearest_mesh': nearest, 'worst_center': worst,
                          'clear': best > 0}
    return results


def probe_envelope_fit(assets, top_node):
    """Sample authored tube circumference against the exterior mesh envelope.

    At each longitudinal slice, intersect the original exterior triangles with
    the slice plane, then bound each sampled tube point by the outermost X
    intersections at its Z. This checks the exterior envelope rather than
    incorrectly treating the original end-cap door art as an open collider.
    """
    item = next(n for n in nodes(assets / 'Mk33ProbeCore.mu') if n['name'] == 'probeCoreMesh')
    triangles = item['verts'][np.array(sum(item['mesh'].submeshes, []))]
    start = np.array([0., -1.5852, .625])
    tested, missing, worst = 0, 0, float('inf')
    for t in np.linspace(.005, .995, 199):
        center = start * (1 - t) + top_node * t
        y = center[1]
        segments = []
        for tri in triangles:
            hits = []
            for a, b in zip(tri, np.roll(tri, -1, axis=0)):
                if (a[1] - y) * (b[1] - y) < 0:
                    hits.append(a + (b - a) * ((y - a[1]) / (b[1] - a[1])))
            if len(hits) == 2:
                segments.append(hits)
        segments = np.array(segments)
        assert len(segments), ('missing exterior cross section', float(y))
        a, b = segments[:, 0], segments[:, 1]
        for angle in np.linspace(0, 2 * np.pi, 65)[:-1]:
            point = center + [.515 * np.cos(angle), 0, .515 * np.sin(angle)]
            z = point[2]
            ids = np.flatnonzero((a[:, 2] - z) * (b[:, 2] - z) < 0)
            if not len(ids):
                missing += 1
                continue
            aa, bb = a[ids], b[ids]
            x = aa[:, 0] + (bb[:, 0] - aa[:, 0]) * (z - aa[:, 2]) / (bb[:, 2] - aa[:, 2])
            margin = float(min(point[0] - x.min(), x.max() - point[0]))
            assert margin > 0, ('authored tube outside source exterior envelope', point.tolist(), margin)
            worst = min(worst, margin)
            tested += 1
    assert missing == 0, ('source envelope slices missing', missing)
    return {'method': '199 longitudinal slices excluding 0.5% terminal edges; 64 circumference samples per slice; outermost original probeCoreMesh X intersections at each point Z.',
            'sampled_points': tested, 'missing_slices': missing,
            'authored_radius_metres': .515,
            'minimum_sampled_exterior_envelope_x_margin_metres': worst,
            'within_sampled_envelope': True,
            'limitation': 'An exterior envelope check, not a claim that original visual caps are physically open or a continuous airtight source hull.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--integration', action='store_true', help='Also verify final generated CFG and combined original/new Krew docking route')
    args = parser.parse_args()
    assets = args.assets
    top_node = point_from_model(assets / 'Mk33ProbeCore.mu', 'node1')
    docking_node = point_from_model(assets / 'dockingNoseCone.mu', 'dockingNode')
    assert np.allclose(top_node, [.0059150452726, 1.37194791559, .76936990023], atol=1e-7)
    assert np.allclose(docking_node, [0, .25995001197, 0], atol=2e-7)

    cockpit_top = np.array([0., 2.75384, 0.])
    probe_bottom = np.array([0., -1.5852, 0.])
    probe_origin = cockpit_top - probe_bottom
    nose_origin = probe_origin + top_node
    probe_rear = PART_TO_INTERNAL @ np.array([0., -1.5852, .625])
    probe_front = PART_TO_INTERNAL @ top_node
    nose_rear = np.zeros(3)
    nose_front = PART_TO_INTERNAL @ docking_node
    rear_in_cockpit = PART_TO_INTERNAL @ probe_origin + probe_rear
    front_in_cockpit = PART_TO_INTERNAL @ nose_origin + nose_front
    assert np.allclose(rear_in_cockpit, [0, -.625, -2.75384])

    before = inspect_front_cap(assets, False)
    after = inspect_front_cap(assets, True)
    assert all(not case['clear'] for case in before.values()), 'Source cap unexpectedly open; check source version'
    assert all(case['clear'] for case in after.values()), after
    report = {
        'in_game_tested': False, 'modulemanager_executed': False,
        'native_meshcutter_executed': False,
        'method': 'Read actual upstream transforms; independently subtract a 32-sided convex cylinder from source triangles. Capsule poses and center segment samples <=5mm; subtract .01m allowance.',
        'part_to_internal_matrix': PART_TO_INTERNAL.tolist(),
        'route': ['Mk33Cockpit.top', 'Mk33ProbeCore.bottom', 'Mk33ProbeCore.topNode',
                  'Mk33DockingNoseCone.bottom01', 'Mk33DockingNoseCone.dockingNode', 'peer docking hatch'],
        'ownership': {'Mk33ProbeCore_has_original_docking_module': False,
                      'docking_module_part': 'Mk33DockingNoseCone',
                      'probe_requires_new_internal': True, 'nose_requires_new_internal': True},
        'source_attach_transforms_part_coordinates': {'probe_topNode': top_node.tolist(),
                                                     'nose_dockingNode': docking_node.tolist()},
        'recommended_iva_endpoints': {'probe_rear': probe_rear.tolist(),
                                      'probe_front': probe_front.tolist(),
                                      'nose_rear': nose_rear.tolist(), 'nose_front': nose_front.tolist()},
        'assembled_in_cockpit_iva': {'probe_origin': (PART_TO_INTERNAL @ probe_origin).tolist(),
                                     'probe_rear': rear_in_cockpit.tolist(),
                                     'nose_origin': (PART_TO_INTERNAL @ nose_origin).tolist(),
                                     'nose_docking_port': front_in_cockpit.tolist()},
        'front_cap_cut': {'targets': ['crewTube', 'Dashboard'], 'radius_metres': .525,
                          'x': 0, 'y': -.6253, 'z_range': [-2.84, -2.64]},
        'front_cap_before': before, 'front_cap_after': after,
        'probe_authored_skin_external_fit': probe_envelope_fit(assets, top_node),
        'limitations': 'This verifies source aperture and attachment geometry only. New authored corridor mesh, native dynamic connection, collider cooking, locomotion and all gameplay require separate checks.'}
    if args.integration:
        interiors, configuration = verify_configuration()
        report['configuration_integration'] = configuration
        report['krew_source_and_authored_route'] = krew_source_and_authored_clearance(assets, interiors)
    destination = ROOT / 'Tests' / 'nose-route-source-checks.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
