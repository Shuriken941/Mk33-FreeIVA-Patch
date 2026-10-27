# Original corridor artwork

The 0.3.5 corridor artwork uses original image-generated slate-blue quilted
insulation, dark ribbed nonslip flooring and ivory aluminum ceiling panels.
Their palette and materials follow the Mk33 interior style; no source mod
textures or meshes are embedded. The PNG files in Models are canonical art
sources. material_sources.json records provenance, dimensions and SHA256 hashes.
Image generation is nondeterministic; the retained PNGs make exact builds reproducible.

Rebuild from this directory using Python 3 with Pillow and Blender 3.4 or later
(the shipped files were generated with Blender 4.3.2):

```sh
python build_materials.py
python build_hatches.py
blender -b --python build_corridors.py
python source_checks/verify_exported_models.py
python validate_corridors.py
python validate_docking_exported.py
```

`build_materials.py` verifies the four canonical wall/floor/ceiling PNGs
(1254 by 1254 pixels) and regenerates only the engineering metal and diffuser
swatches. The historical corridorWallWarm filename now contains the same
blue quilted fabric as corridorWall, so both walls have a coherent palette.
The light ceiling and dark longitudinal floor ribs establish orientation.
No corridor mesh, UV, collider, fixture, ladder or native docking transform
changes in this visual update; all existing physical geometry remains intact.
The script never overwrites independent hatch artwork.

The Cockpit corridor has five main-ceiling fixtures plus one shaft-ceiling
fixture, each with its own point light. The short Airlock bridge has one point light. The telescoping docking
tube has two fixtures and two lights, along with an independent Ladder trigger
that scales with the tube length. Point-light culling masks include only layers
16 and 20. Fixtures have no new solid colliders and sit outside the central
travel envelope.

The Krew docking passage now lines the original central shaft. Its side entry
starts at the central AIRLOCK door around `(0,1.055827,.096354)` and turns upward
on the native axis `(0,Y,.61551148)`. The lining reaches Y1.80 and has a 0.39 m
bore radius, plus a rectangular entrance neck aligned to the original door.
Mounted wall fixtures illuminate the shaft. The former outside transfer gallery
and central roof seal are removed. The separate aft KrewAirlockBridge remains.

The docking sleeve is an uncapped inward-facing cylinder, radius 0.39 m and
unit length along local negative Y. Its root is `(0,1.80,.61551148)`, X180.
Native FreeIVA controls the named child's visibility, length and ladder trigger.
Its dimensions fit within the native port's approximately 0.399 m inner lip.

The live circular pressure hatches reuse the installed FreeIVA Size1 leaf and
both handle renderers. They retain the original full-size primitive pressure seal;
a small opaque insert closes the reused leaf's porthole. Opening hides all visible
door components and the solid seal together. Persistent click targets remain on
both sides. No FreeIVA colliders, animation, frame, tube or cutout are copied.
The legacy CircularHatch.mu is retained for tooling compatibility; direct runtime
modules provide the live hatch behavior. See README-classic-hatches.md if present.

For a Blender preview of the actual exported Cockpit `.mu` (not a gameplay
screenshot):

```sh
blender -b --python preview_assets.py -- /path/to/corridor-preview.png
blender -b --python preview_assets.py -- /path/to/krew-passage-preview.png KrewDockPassage
```

The preview imports the authored `.mu`, including its UVs, materials, transforms
and point lights. It uses Blender lighting and therefore does not validate KSP
rendering, Unity lighting intensity, hatch interaction or traversal.

Version 0.3.1 fits metal housings to actual exported shell triangles. Each
separate white diffuser uses corridorLight; every backing overlaps the skin by
1 mm. The access ladder has eight rungs, two continuous rails and six spacers
bolted to the real rear shaft wall, above the open main-bore intersection.
Run `python verify_fixtures.py` to verify backing contact, the support graph
and visible-hardware clearance. Baseline invariance applies only to versions
with the same physical route; 0.3.4 intentionally replaces the Krew route.
