"""Validate canonical source art and rebuild small engineering material maps.
SPDX-License-Identifier: MIT. Python 3 + Pillow.

The 0.3.5 wall/floor/ceiling PNGs are original image-generated source artwork.
They are retained directly in Models, with hashes and provenance recorded in
material_sources.json. They cannot be reconstructed deterministically from a
prompt. This script verifies them and never replaces them with the old 0.3.4
procedural placeholder panels. It does not regenerate hatchGrey.png, which is
owned by the independent hatch artwork pipeline.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'Models'
source = json.loads((ROOT / 'Source/material_sources.json').read_text())
for texture in source['textures']:
    path = ROOT / texture['file']
    assert path.is_file(), 'Missing canonical art source: ' + str(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == texture['sha256'], 'Art source hash mismatch: ' + str(path)
    with Image.open(path) as image:
        assert list(image.size) == texture['dimensions'], path
        assert image.mode == texture['mode'], path

# Original neutral engineering swatch for rails, lamp housings and supports.
im = Image.new('RGB', (32, 32))
im.putdata([(121+(y%5)-2, 128+(y%5)-2, 132+(y%5)-2)
            for y in range(32) for x in range(32)])
im.save(OUT / 'corridorGrey.png')
# Diffuser map preserves the unchanged fixture geometry/material references.
im = Image.new('RGB', (512, 512), (229,235,232))
d = ImageDraw.Draw(im)
for y in range(0,512,16):
    d.line((0,y,511,y), fill=(199,210,207), width=2)
    d.line((0,y+3,511,y+3), fill=(242,246,241), width=1)
d.rectangle((2,2,509,509), outline=(188,201,197), width=3)
im.save(OUT / 'corridorLight.png')
print('Verified 4 canonical corridor maps; rebuilt metal and diffuser maps. Hatch art unchanged.')
