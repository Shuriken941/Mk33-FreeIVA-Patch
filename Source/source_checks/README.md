# Optional checks against installed originals

These scripts require Python 3, NumPy and SciPy, plus your installed original
Mk-33 assets. They never ship or write copies of those meshes. Example:

```sh
python validate_original_apertures.py --assets "/path/to/KSP/GameData/WildBlueIndustries/Mk-33/Parts/SharedAssets"
python validate_other_apertures.py --assets "/path/to/KSP/GameData/WildBlueIndustries/Mk-33/Parts/SharedAssets"
```

They independently subtract convex cut volumes from original triangle surfaces
and sample selected upright capsule paths. They do not execute Unity PhysX,
FreeIVA MeshCutter2, ModuleManager, seating, gravity locomotion or EVA.
Clearance data applies only to those sampled routes and exact asset versions.
The archived original report additionally includes manually recorded baseline
obstructions and native cut parameters; rerun output focuses on measured paths.

`mu.py` is the GPL-2.0-or-later parser by taniwha/io_object_mu:
<https://github.com/taniwha/io_object_mu/blob/master/mu.py>.
Its original license header is retained. See `../../LICENSES/GPL-2.0.txt`.
The surrounding inspection/check code is GPL-2.0-or-later.
