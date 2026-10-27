"""Sequential regression for the KSPCommunityFixes 1.41.1 .mu reader.

SPDX-License-Identifier: GPL-2.0-or-later.

Independent Python implementation of the relevant sequential reader behavior;
does not import io_object_mu/mu.py. Source: KSPModdingLibs/KSPCommunityFixes,
commit 7969fdc50bf4e350193abe5ba2e89533b12ca02f, Library/MuParser.cs:
ReadChild (132), ReadMeshRenderer (378), ReadMaterials (425),
ReadMaterial4 (533), ReadMaterialTexture (568), ReadTextures (577),
ReadMesh (799). Source license applies to the ported reader behavior.

The critical old reader contract is preserved deliberately:
  renderer references grow matDummies up to their highest material index;
  ReadMaterials indexes matDummies[i] BEFORE reading material i;
  ReadTextures requires texCount == textureDummies.Count and binds immediately.

Unity GameObjects, shaders, texture decoding, physics and KSP are not executed.
Only this package's emitted v5 structural component subset is implemented;
unknown components fail explicitly instead of being guessed or skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = 'https://github.com/KSPModdingLibs/KSPCommunityFixes/blob/7969fdc50bf4e350193abe5ba2e89533b12ca02f/KSPCommunityFixes/Library/MuParser.cs'
SOURCE_SHA256 = '0374d56de3595efaf4832adab2491bb5c62577ea0b6fb863408068b9edf29951'


class MaterialRangeError(IndexError):
    pass


class MuReader1411:
    def __init__(self, data: bytes, *, guard_unused_materials: bool = False):
        self.data = data
        self.index = 0
        self.guard_unused_materials = guard_unused_materials
        self.mat_dummies: list[list[int]] = []
        self.texture_dummies: list[list[tuple[int, str]]] = []
        self.renderers: list[dict] = []
        self.materials: list[dict] = []
        self.textures: list[str] = []
        self.geometry = hashlib.sha256()
        self.component_counts: dict[str, int] = {}
        self.failure_details = None
        self.material_block_count = 0
        self.texture_block_count = 0

    def take(self, count: int) -> bytes:
        if count < 0 or self.index + count > len(self.data):
            raise ValueError(f'Unable to read beyond end of data at {self.index}, size {count}')
        chunk = self.data[self.index:self.index + count]
        self.index += count
        return chunk

    def integer(self) -> int:
        return struct.unpack('<i', self.take(4))[0]

    def string(self) -> str:
        size = 0
        for shift in range(0, 35, 7):
            b = self.take(1)[0]
            size |= (b & 127) << shift
            if not b & 128:
                return self.take(size).decode('utf-8')
        raise ValueError('Invalid 7-bit encoded string length')

    def vector(self, count: int) -> list[float]:
        return list(struct.unpack('<' + 'f' * count, self.take(4 * count)))

    def count(self, key: str) -> None:
        self.component_counts[key] = self.component_counts.get(key, 0) + 1

    def mesh(self) -> None:
        start = self.index
        if self.integer() != 13:
            raise ValueError('Mesh Error: expected MeshStart')
        size = self.integer()
        submesh_count = self.integer()
        if size < 0 or submesh_count < 0:
            raise ValueError('Negative mesh size')
        while True:
            kind = self.integer()
            if kind == 22:
                break
            stride = {14: 12, 15: 8, 16: 8, 17: 12, 18: 16, 20: 32, 32: 4}.get(kind)
            if stride is not None:
                self.take(size * stride)
            elif kind == 19:
                count = self.integer()
                if count < 0 or count % 3:
                    raise ValueError('Invalid triangle count')
                self.take(count * 4)
            elif kind == 21:
                self.take(self.integer() * 64)
            else:
                raise ValueError(f'Unsupported mesh entry {kind} at {self.index - 4}')
        self.geometry.update(self.data[start:self.index])

    def mesh_renderer(self, path: str) -> None:
        start = self.index
        self.take(2 if self.version >= 1 else 0)
        count = self.integer()
        self.geometry.update(self.data[start:self.index])
        renderer_id = len(self.renderers)
        renderer = {'path': path, 'slots': [], 'bound_material': None}
        self.renderers.append(renderer)
        for _ in range(count):
            material_index = self.integer()
            if material_index < 0:
                raise MaterialRangeError('Negative renderer material index')
            # Exact sequential growth of KSPCF 1.41.1 ReadMeshRenderer.
            while material_index >= len(self.mat_dummies):
                self.mat_dummies.append([])
            self.mat_dummies[material_index].append(renderer_id)
            renderer['slots'].append(material_index)

    def read_materials(self) -> None:
        self.material_block_count += 1
        count = self.integer()
        for i in range(count):
            # Deliberately preserve the observed failure. KSPCF performs this
            # list index BEFORE ReadMaterial4, even for defined-unused entries.
            if i >= len(self.mat_dummies) and not self.guard_unused_materials:
                self.failure_details = {'stage': 'ReadMaterials', 'material_index': i,
                                        'material_count': count, 'mat_dummies_count': len(self.mat_dummies),
                                        'byte_offset': self.index}
                raise MaterialRangeError(f'ReadMaterials: matDummies[{i}] out of range (Count={len(self.mat_dummies)})')
            renderers = self.mat_dummies[i] if i < len(self.mat_dummies) else []
            name, shader = self.string(), self.string()
            properties = {}
            for _ in range(self.integer()):
                prop, kind = self.string(), self.integer()
                if kind in (0, 1):
                    value = self.vector(4)
                elif kind in (2, 3):
                    value = self.vector(1)[0]
                elif kind == 4:
                    texture_index = self.integer()
                    if texture_index < 0:
                        raise ValueError('Negative material texture index')
                    while texture_index >= len(self.texture_dummies):
                        self.texture_dummies.append([])
                    self.texture_dummies[texture_index].append((i, prop))
                    value = {'texture_index': texture_index, 'scale': self.vector(2), 'offset': self.vector(2)}
                else:
                    raise ValueError(f'Unsupported material property {kind}')
                properties[prop] = {'type': kind, 'value': value}
            self.materials.append({'name': name, 'shader': shader, 'properties': properties})
            for renderer_id in renderers:
                self.renderers[renderer_id]['bound_material'] = i

    def read_textures(self) -> None:
        self.texture_block_count += 1
        count = self.integer()
        # Old KSPCF returns immediately on mismatch, leaving the block payload
        # unconsumed. Treat that logged error as a failed model regression.
        if count != len(self.texture_dummies):
            raise ValueError(f'TextureError: {count} {len(self.texture_dummies)}')
        for i in range(count):
            name, kind = self.string(), self.integer()
            self.textures.append(name)
            for material_id, prop in self.texture_dummies[i]:
                self.materials[material_id]['properties'][prop]['value'].update(texture=name, texture_type=kind)

    def child(self, parent: str = '') -> None:
        start = self.index
        name = self.string()
        path = parent + '/' + name
        self.take(40)  # position, quaternion, scale
        self.geometry.update(self.data[start:self.index])
        while self.index < len(self.data):
            token = self.integer()
            if token == 0:
                self.child(path)
            elif token == 1:
                return
            elif token == 7:
                self.count('MeshFilter'); self.geometry.update(b'MeshFilter'); self.mesh()
            elif token == 8:
                self.count('MeshRenderer'); self.geometry.update(b'MeshRenderer'); self.mesh_renderer(path)
            elif token == 10:
                self.read_materials()
            elif token == 12:
                self.read_textures()
            elif token == 23:
                self.count('Light'); self.geometry.update(b'Light' + self.take(36 if self.version > 1 else 32))
            elif token == 24:
                start = self.index; self.string(); self.take(4)
                self.geometry.update(b'TagAndLayer' + self.data[start:self.index])
            elif token in (3, 25):
                self.count('MeshCollider'); self.geometry.update(bytes([token]) + self.take(2 if token == 25 else 1)); self.mesh()
            elif token in (6, 28):
                self.count('BoxCollider'); self.geometry.update(bytes([token]) + self.take(25 if token == 28 else 24))
            elif token in (4, 26):
                self.count('SphereCollider'); self.geometry.update(bytes([token]) + self.take(17 if token == 26 else 16))
            elif token in (5, 27):
                self.count('CapsuleCollider'); self.geometry.update(bytes([token]) + self.take(25 if token == 27 else 20))
            else:
                raise ValueError(f'Unsupported object component {token} at {self.index - 4}')

    def parse(self) -> dict:
        if self.integer() != 76543:
            raise ValueError('Invalid mu file')
        self.version = self.integer()
        if self.version != 5:
            raise ValueError(f'This regression targets emitted v5 files, got {self.version}')
        self.string()  # model name
        self.child()
        if self.index != len(self.data):
            raise ValueError('Trailing unparsed model bytes')
        if self.material_block_count != 1 or self.texture_block_count != 1:
            raise ValueError('Expected exactly one material table and one texture table')
        mappings = []
        for renderer in self.renderers:
            if len(renderer['slots']) != 1 or renderer['bound_material'] is None:
                raise ValueError('Each authored renderer must have exactly one bound material')
            material = self.materials[renderer['bound_material']]
            semantic = {'name': material['name'], 'shader': material['shader'], 'properties': {}}
            for prop, data in material['properties'].items():
                value = data['value']
                if data['type'] == 4:
                    if 'texture' not in value:
                        raise ValueError(f'Unbound texture for {renderer["path"]}: {prop}')
                    value = {k: v for k, v in value.items() if k != 'texture_index'}
                semantic['properties'][prop] = {'type': data['type'], 'value': value}
            mappings.append({'renderer': renderer['path'], 'material': semantic})
        return {'geometry_sha256': self.geometry.hexdigest(), 'renderers': mappings,
                'material_count': len(self.materials), 'texture_count': len(self.textures),
                'mat_dummies_count': len(self.mat_dummies), 'component_counts': self.component_counts,
                'all_renderer_materials_and_textures_bound': True}


def check(data: bytes, *, tolerant: bool = False) -> dict:
    reader = MuReader1411(data, guard_unused_materials=tolerant)
    try:
        return {'accepted': True, **reader.parse()}
    except (IndexError, ValueError, UnicodeDecodeError, struct.error) as error:
        return {'accepted': False, 'error': str(error), 'details': reader.failure_details}


def negative_fixture() -> bytes:
    """No proprietary/game data: renderer0 references mat0, mat1 is unused."""
    payload = bytearray()
    def ints(*values): payload.extend(struct.pack('<' + 'i' * len(values), *values))
    def string(value):
        raw = value.encode(); assert len(raw) < 128
        payload.extend(bytes([len(raw)])); payload.extend(raw)
    ints(76543, 5); string('RegressionUnusedMaterial'); string('Root')
    payload.extend(struct.pack('<10f', 0, 0, 0, 0, 0, 0, 1, 1, 1, 1))
    ints(8); payload.extend(b'\x00\x00'); ints(1, 0)
    ints(10, 2)
    for name in ['Used', 'TrailingUnused']:
        string(name); string('KSP/Diffuse'); ints(0)
    ints(12, 0)
    return bytes(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-models', type=Path, help='Optional previous release Models directory')
    parser.add_argument('--kspcf-source', type=Path, help='Optional exact upstream MuParser.cs to fingerprint')
    parser.add_argument('--models', type=Path, default=ROOT / 'Models')
    parser.add_argument('--report', type=Path, default=ROOT / 'Tests' / 'kspcf-mu-reader-checks.json')
    args = parser.parse_args()
    source_verified = None
    if args.kspcf_source:
        source_verified = hashlib.sha256(args.kspcf_source.read_bytes()).hexdigest() == SOURCE_SHA256
        assert source_verified, 'Exact KSPCF 1.41.1 source fingerprint mismatch'
    report = {'in_game_tested': False, 'unity_executed': False,
              'reader': 'Independent sequential port of KSPCF 1.41.1 relevant v5 component subset',
              'source_url': SOURCE_URL, 'source_sha256': SOURCE_SHA256, 'source_fingerprint_verified': source_verified,
              'negative_trailing_unused_material_fixture': check(negative_fixture()), 'models': {}}
    assert not report['negative_trailing_unused_material_fixture']['accepted']
    assert report['negative_trailing_unused_material_fixture']['details']['stage'] == 'ReadMaterials'
    expected_old_failures = {'CircularHatch.mu', 'InteractionPoints.mu', 'KrewAirlockBridge.mu'}
    old_failures = set()
    for path in sorted(args.models.glob('*.mu')):
        current = check(path.read_bytes())
        assert current['accepted'], (path.name, current)
        # Detailed renderer mappings are compared in memory; keep the report readable.
        item = {k: v for k, v in current.items() if k != 'renderers'}
        if args.baseline_models:
            before_path = args.baseline_models / path.name
            before_bytes = before_path.read_bytes()
            old = check(before_bytes)
            if not old['accepted']:
                old_failures.add(path.name)
            old_semantic = check(before_bytes, tolerant=True)
            assert old_semantic['accepted'], (path.name, old_semantic)
            assert current['geometry_sha256'] == old_semantic['geometry_sha256'], ('Geometry changed', path.name)
            assert current['renderers'] == old_semantic['renderers'], ('Renderer shader/texture mapping changed', path.name)
            item['previous_release_result'] = {k: v for k, v in old.items() if k != 'renderers'}
            item['geometry_preserved'] = True
            item['renderer_shader_texture_mappings_preserved'] = True
        report['models'][path.name] = item
    assert len(report['models']) == 8, 'Expected all 8 authored model files'
    if args.baseline_models:
        assert old_failures == expected_old_failures, old_failures
        report['previous_release_failures_match_observed_three_models'] = True
    args.report.parent.mkdir(exist_ok=True, parents=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
