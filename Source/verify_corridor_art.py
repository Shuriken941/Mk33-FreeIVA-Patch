"""Verify v0.3.5 corridor art sources and unchanged physical model exports.
SPDX-License-Identifier: MIT. Does not execute Unity or KSP.
"""
from pathlib import Path
import argparse, hashlib, json, sys
from PIL import Image
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'Source/source_checks'))
from mu import Mu

def walk(o):
    yield o
    for c in o.children: yield from walk(c)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

ap=argparse.ArgumentParser()
ap.add_argument('--baseline', type=Path)
args=ap.parse_args()
report={'in_game_tested':False,
        'scope':'Canonical texture files, texture references, optional complete exported corridor model byte comparison against 0.3.4. Blender previews reviewed separately; no Unity lighting claim.',
        'textures':{},'models':{}}
source=json.loads((ROOT/'Source/material_sources.json').read_text())
for record in source['textures']:
    p=ROOT/record['file']
    assert sha(p)==record['sha256'],p
    with Image.open(p) as im:
        assert list(im.size)==record['dimensions'] and im.mode=='RGB',p
        assert min(im.size)>=1024,p
        report['textures'][p.name]={'sha256':sha(p),'dimensions':list(im.size),'opaque':True,'source_matches':True}
assert (ROOT/'Models/corridorWall.png').read_bytes()==(ROOT/'Models/corridorWallWarm.png').read_bytes()
for stem in ['CockpitCorridor','KrewAirlockBridge','KrewDockPassage','KrewDockTube','ProbeCorePassage','NoseDockPassage']:
    path=ROOT/'Models'/(stem+'.mu');mu=Mu().read(str(path))
    refs={mu.textures[t.index].name for material in mu.materials for t in material.textureProperties.values()}
    assert 'corridorWall' in refs,stem
    assert all((ROOT/'Models'/(name+'.png')).is_file() for name in refs),stem
    data={'sha256':sha(path),'texture_references_resolve':True,'textures':sorted(refs)}
    if args.baseline:
        baseline=args.baseline/'Models'/path.name
        assert path.read_bytes()==baseline.read_bytes(),('Corridor export changed',stem)
        data['byte_identical_to_v034']=True
        data['collisions_fixtures_ladders_uvs_native_tube_transforms_unchanged']=True
    report['models'][stem]=data
(ROOT/'Tests/corridor-art-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
