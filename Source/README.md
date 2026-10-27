# Mk33FreeIVA 0.3.5 source

Build target KSP 1.12.5 / Unity 2019.4 / FreeIVA 0.2.20.2.
The shipped binary links to actual public API references; no foreign DLL ships.

```sh
KSP_MANAGED="/path/to/KSP/KSP_x64_Data/Managed" \
FREEIVA_DLL="/path/to/KSP/GameData/FreeIva/Plugins/FreeIva.dll" \
MK33_DOTNET="/path/to/dotnet" bash build.sh
```

`build.sh` compiles all three C# files with Roslyn without NuGet restore.
The csproj provides the same source list for IDE builds.

- `Mk33FreeIvaGeometry`: validates required pressure caps, original doors and
  authored shells before native source cuts, then constructs matching physical
  shells. Missing/incomplete shell disables unbuckling on its own part.
- `Mk33FreeIvaPressureHatch`: direct-INTERNAL classic FreeIVA door rendering over the existing
  primitive solid plate, persistent click targets, native FreeIVA hatch behavior
  plus explicit closed initialization and physical-connection/readiness gates.
- `Mk33FreeIvaAuthoredShell`: validates prebuilt authored shell colliders without
  duplicating them, then supplies the common complete-shell marker.
- `Mk33FreeIvaWalkGate`: coordinates per-part readiness blockers and restores
  only permission disabled by this patch. Pending Awake does not disable seats;
  final checks run after loading. Configured seatless-part restrictions remain.
- `Mk33FreeIvaHatch`: adapts original doors, keeps their handles correctly placed,
  and adds closed-state/connection/readiness validation. The Krew central AIRLOCK
  door is extracted from cabinMesh with its UV/materials and handles intact. It
  opens automatically only with a physical, deployed FreeIVA docking connection.
  The separate roof crewDoor remains bound only to the original EVA airlock.
  The cockpit lower EXIT handle uses the same adapter for native side-door EVA;
  the original EXIT wall and door stay physically closed.
- `Mk33FreeIvaWindowMask`: window-only native depth shader at queue 998, private
  runtime material, binding and camera-state repair; installed glass is unchanged.
- `Mk33FreeIvaColliderSetup`: restores nonconvex collision for explicitly named
  imported passage shells and docking tubes before readiness checks. Trigger,
  disabled, wrong-layer, missing and empty colliders still fail validation.
- `generate_patch.py`: current direct-module configuration; no circular PROP placements.
- `README-visual-assets.md` and `README-nose-passages.md`: model generation.

Checks (Python 3, NumPy/SciPy/Pillow as required):

```sh
python verify_package.py --gamedata /path/to/KSP/GameData
python verify_kspcf_mu.py
python source_checks/verify_exported_models.py
python validate_corridors.py
python validate_docking_exported.py
python verify_nose_passages.py
python verify_v030.py --assets /path/to/Mk-33/Parts/SharedAssets --integration
python source_checks/validate_other_apertures.py --assets /path/to/Mk-33/Parts/SharedAssets
python source_checks/validate_window_sources.py /path/to/Mk-33
MK33_DOTNET=/path/to/dotnet python tests/pressure_runtime/run.py
```

The exact-source behavior harness uses dependency doubles. It does not run Unity,
PhysX, KSP, ModuleManager or native FreeIVA coroutines. Read its own README and
Tests/VALIDATION.md for evidence limits. Geometry checks likewise do not prove gameplay.

Helper/config code GPL-2.0-or-later; authored asset code/art MIT.
