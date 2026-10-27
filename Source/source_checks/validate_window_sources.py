"""Inspect installed windows used by the runtime depth prepass (GPL-2.0-or-later).

Usage: python validate_window_sources.py <Mk-33 repo or installed Mk-33 folder>
Requires numpy/scipy and the supplied mu reader. Does not copy any original art.
"""
import json
import sys
from pathlib import Path

import numpy as np

from inspect_mu import nodes
from mu import Mu


def main():
    root = Path(sys.argv[1])
    shared = next(iter(root.rglob('cockpitIVA.mu'))).parent
    cases = [
        ('cockpitIVA', [(0, -.6503, -1.64), (0, 1.496873, -.044039), (0, -.6253, -2.72)], .525),
        ('crewModuleIVA', [(0, -.025, -1.23), (0, -.025, 1.08),
                           (1.11893, 1.82830, .76054), (0, 1.82, .61551148), (0, 1.055827, .096354)], .525),
        ('controlCabIVA', [(0, 1.644332, .17)], .5),
    ]
    result = {'source': str(root), 'in_game_tested': False, 'checks': []}
    for name, apertures, radius in cases:
        path = shared / (name + '.mu')
        windows = [n for n in nodes(path) if n['name'] == 'windows']
        assert len(windows) == 1, name + ': missing or ambiguous windows transform'
        entry = windows[0]
        vertices = entry['verts']
        lower, upper = vertices.min(0), vertices.max(0)
        # An AABB separation test is conservative: if the whole window bounds
        # miss the sphere around a hatch centre, no cloned window triangle can
        # span that hatch. This independently guards against masking a tunnel.
        clearances = []
        for aperture in apertures:
            offset = np.maximum(np.maximum(lower - aperture, np.array(aperture) - upper), 0)
            distance = float(np.linalg.norm(offset))
            assert distance > radius, (name, aperture, distance)
            clearances.append(round(distance - radius, 6))
        model = Mu().read(str(path))
        material = model.materials[entry['object'].renderer.materials[0]]
        result['checks'].append({
            'model': name,
            'window_triangles': len(sum(entry['mesh'].submeshes, [])),
            'window_shader': material.shaderName,
            'bounds_unity': [lower.tolist(), upper.tolist()],
            'aperture_clearance_lower_bound_metres': clearances,
            'pass': True,
        })
    destination = Path(__file__).resolve().parents[2] / 'Tests' / 'window-source-checks.json'
    destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Window sources: all hatch apertures clear; report:', destination)


if __name__ == '__main__':
    main()
