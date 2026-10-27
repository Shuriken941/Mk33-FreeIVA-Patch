# Classic pressure hatch visuals in 0.3.5

`Mk33FreeIvaPressureHatch` reads the installed model
`FreeIva/Props/FreeIva_Hatch_Round_Size1` with `GameDatabase.GetModelPrefab`.
It copies only the mesh renderers under `Hatch_Size1_Door`: the leaf and its
interior/exterior handles. The closed hinge pose is baked relative to the model
root, then the nominal 0.41 m leaf radius is fitted to the existing 0.545 m seal.
The original atlas, normal map, UVs, materials and detailed hardware are retained.

No original art is included in this patch. The materials remain read-only shared
assets; mesh copies are private. No external model, original mod file, native
frame, animated component, cutout, tube, rail or imported collider is modified or
copied. The existing FreeIVA dependency supplies the art; there is no new mod
dependency.

The original classic leaf has a small central porthole. A blue-gray opaque
0.145 m radius insert fills it. This changes only the generated render mesh;
the full 1.09 x 0.06 x 1.09 m solid box seal remains exactly as in 0.3.4.
The classic leaf, both visible handles and insert are children of the existing
pressure door and disappear together when opened. Its persistent layer-20
interaction targets remain available to close it again. No opening animation is
used. Original Mk-33 AIRLOCK and cockpit door artwork are handled separately.

If the optional classic visual cannot be read or validated, loading continues
with the full opaque generated plate and its existing handles. The partial
classic copy stays inactive. This cosmetic fallback does not disable unbuckling,
change native docking checks or authorize an unsafe passage.

Validation:

- `tests/pressure_runtime/run.py`: production C# with deterministic dependency
  doubles, including optional-art success/failure, immutable meshes/materials,
  source-pose baking, opaque insert, unchanged seal, opening/closing and docking.
- `source_checks/verify_classic_hatch.py --freeiva /path/to/GameData/FreeIva`:
  reads the actual installed `.mu`, records provenance and geometry bounds, and
  checks the composite leaf/insert against the existing 0.525 m aperture with
  9,285 projected samples from **each** side with back-face culling.
- `build.sh`: separate compilation against actual KSP, Unity and FreeIVA APIs.

These are numerical, API and dependency-double checks. They do not execute KSP,
Unity rendering, native IVA loading or PhysX. Private Blender previews of the
installed model are used for visual review, not presented as gameplay evidence.
