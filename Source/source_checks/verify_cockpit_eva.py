"""Verify lower cockpit EXIT interaction against installed original Mk-33 art.

This is source/config/geometry validation, not KSP, Unity or a live EVA test.
No original art is written to the report. GPL-2.0-or-later.
"""
from pathlib import Path
import argparse, ast, hashlib, json, sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from inspect_mu import nodes

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Source'))
from verify_package import parse, value

def vector(text):
    return np.array([float(x) for x in text.split(',')])

def modules(node, name):
    return [n for n in node['nodes'] if value(n, 'name') == name]

def cockpit(config):
    return next(n for n in parse(config.read_text()) if n['type'].startswith('@INTERNAL[wbiMk33CockpitSpace]'))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', type=Path, required=True)
    ap.add_argument('--baseline', type=Path, help='Optional V0.3.4 package root')
    ap.add_argument('--freeiva-source', type=Path, help='Optional exact FreeIVA source checkout')
    ap.add_argument('--output', type=Path, default=ROOT / 'Tests/cockpit-eva-checks.json')
    args = ap.parse_args()
    cfg = ROOT / 'Patches/Mk33_FreeIVA.cfg'
    space = cockpit(cfg)
    geometry = modules(space, 'Mk33FreeIvaGeometry')[0]
    hatch = next(n for n in modules(space, 'Mk33FreeIvaHatch') if value(n, 'doorTransformName') == 'Mk33CockpitLowerEvaHandle')
    assert value(hatch, 'airlockName') == 'Airlock,0'
    assert value(hatch, 'attachNodeId') == ''
    assert value(hatch, 'dockingPortNodeName') in (None, '')
    assert value(hatch, 'tubeTransformName') in (None, '')
    assert value(hatch, 'autoOpenWhenDocked') in (None, 'false')
    assert value(hatch, 'extractSourceTransform') == 'Dashboard'
    assert ('requiredOriginalDoor', 'Mk33CockpitLowerEvaHandle') in geometry['values']
    assert space['nodes'].index(hatch) < space['nodes'].index(geometry)
    trigger = next(n for n in hatch['nodes'] if n['type'] == 'HandleCollider')
    trigger_size = vector(value(trigger, 'dimensions'))
    assert np.all(trigger_size >= [.19, .31, .31])
    lo, hi = vector(value(hatch, 'extractBoundsMin')), vector(value(hatch, 'extractBoundsMax'))
    iva = args.assets / 'cockpitIVA.mu'
    source = next(e for e in nodes(iva) if e['name'] == 'Dashboard')
    vertices = source['verts']
    faces = np.array(sum(source['mesh'].submeshes, []))
    inside = np.all((vertices >= lo) & (vertices <= hi), axis=1)
    chosen = inside[faces].all(axis=1)
    extracted, retained = faces[chosen], faces[~chosen]
    assert len(extracted) == int(value(hatch, 'extractExpectedTriangles')) == 104
    assert len(extracted) + len(retained) == len(faces)
    # Every original triangle is preserved: only original handle ownership changes.
    _, weld = np.unique(np.round(vertices, 5), axis=0, return_inverse=True)
    edges = np.vstack([weld[extracted[:, [0, 1]]], weld[extracted[:, [1, 2]]], weld[extracted[:, [2, 0]]]])
    _, labels = connected_components(coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(weld.max()+1, weld.max()+1)), directed=False)
    component_counts = sorted(int((labels[weld[extracted[:, 0]]] == label).sum()) for label in np.unique(labels[weld[extracted[:, 0]]]))
    assert component_counts == [20, 28, 56]
    # The extracted handles cannot share a welded point with the wall/door leaf.
    assert not set(weld[extracted].reshape(-1)).intersection(weld[retained].reshape(-1))
    # Prove the retained EXIT leaf still closes the lower side wall: every ray
    # in a grid behind/around the control crosses retained source triangles.
    tree = ast.parse((ROOT / 'Source/validate_corridors.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'point_triangle', 'segment_segment', 'segment_triangle'}]
    scope = {'np': np}
    exec(compile(tree, 'capsule-distance-functions', 'exec'), scope)
    triangles = vertices[retained]
    max_gap = 0.
    probes = 0
    for y in np.linspace(-.70, -.30, 17):
        for z in np.linspace(-2.48, -2.18, 17):
            distance = float(np.sqrt(scope['segment_triangle'](np.array([2.0, y, z]), np.array([3.2, y, z]), triangles).min()))
            max_gap = max(max_gap, distance)
            probes += 1
    assert max_gap < 1e-7, ('Retained EXIT leaf has an unexpected opening', max_gap)
    external = args.assets / 'Mk33Cockpit.mu'
    airlocks = [e for e in nodes(external) if e['name'] == 'Airlock']
    assert len(airlocks) == 2
    exit_node = airlocks[0]
    assert exit_node['object'].tag_and_layer.tag == 'Airlock'
    assert exit_node['object'].collider.isTrigger
    exterior_position = exit_node['matrix'][:3, 3][[0, 2, 1]]
    assert np.allclose(exterior_position, [-3.04065979749, 2.23699762776, .62999999097], atol=1e-7)
    # Standard KSP part-to-IVA axis mapping: (-x,-z,-y).
    exterior_in_iva = -exterior_position[[0, 2, 1]]
    handle_position = vector(value(hatch, 'position'))
    separation = float(np.linalg.norm(exterior_in_iva - handle_position))
    assert separation < .50
    report = {
        'in_game_tested': False,
        'scope': 'Original model/config audit and triangle geometry. Native EVA source checked when --freeiva-source is provided. Does not execute KSP spawning, obstruction checks or Physics.',
        'patch_sha256': hashlib.sha256(cfg.read_bytes()).hexdigest(),
        'original_cockpit_iva_sha256': hashlib.sha256(iva.read_bytes()).hexdigest(),
        'original_external_model_sha256': hashlib.sha256(external.read_bytes()).hexdigest(),
        'binding': 'Airlock,0',
        'native_external_exit_tag_and_trigger_valid': True,
        'native_external_exit_part_position_m': exterior_position.tolist(),
        'handle_to_native_exit_separation_m': separation,
        'extracted_handle_triangles': len(extracted),
        'extracted_components_triangles': component_counts,
        'retained_dashboard_triangles': len(retained),
        'original_leaf_wall_retained': True,
        'all_original_triangles_preserved_between_source_and_extracted_handle': True,
        'extracted_handle_disjoint_from_leaf_wall': True,
        'retained_leaf_grid_probes': probes,
        'maximum_ray_gap_m': max_gap,
        'interaction_trigger_dimensions_m': trigger_size.tolist(),
        'interaction': 'Use UNLOCK area on the existing lower EXIT door. Native FreeIVA performs stock EVA immediately, retaining closed art/shell; no unsealed walking hole is created.'
    }
    if args.baseline:
        previous = cockpit(args.baseline / 'Patches/Mk33_FreeIVA.cfg')
        prev_geometry = modules(previous, 'Mk33FreeIvaGeometry')[0]
        assert geometry['nodes'] == prev_geometry['nodes'], 'A cockpit cut was added/changed'
        expected_values = prev_geometry['values'] + [('requiredOriginalDoor', 'Mk33CockpitLowerEvaHandle')]
        assert sorted(geometry['values']) == sorted(expected_values)
        current_original = [n for n in modules(space, 'Mk33FreeIvaHatch') if n is not hatch]
        assert current_original == modules(previous, 'Mk33FreeIvaHatch')
        assert modules(space, 'Mk33FreeIvaPressureHatch') == modules(previous, 'Mk33FreeIvaPressureHatch')
        report['baseline_cockpit_all_existing_hatch_settings_and_cuts_unchanged'] = True
    if args.freeiva_source:
        native_path = args.freeiva_source / 'FreeIva/InternalModules/Hatches/Hatch.cs'
        native = native_path.read_text(encoding='utf-8-sig')
        assert 'airlockTransform = FindAirlock(part, airlockName);' in native
        assert 'if (open && interaction == Interaction.EVA)\n\t\t\t{\n\t\t\t\tGoEVA();' in native
        assert 'return airlockTransform == null || FlightEVA.HatchIsObstructed(part, airlockTransform)' in native
        assert 'kerbal.protoCrewMember.type != ProtoCrewMember.KerbalType.Tourist' in native
        report['native_source_sha256'] = hashlib.sha256(native_path.read_bytes()).hexdigest()
        report['native_eva_dispatch_and_obstruction_tourist_checks_retained'] = True
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
