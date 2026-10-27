# Mk33FreeIVA geometry helper source

Build target: Kerbal Space Program 1.12.5 (Unity 2019.4), FreeIVA 0.2.20.2.
The delivered DLL is compiled against those actual public API reference assemblies,
not hand-written stand-ins. The reference DLLs are build inputs only and are not
included in this package.

Linux/macOS with a .NET SDK:

```sh
KSP_MANAGED="/path/to/KSP/KSP_x64_Data/Managed" \
FREEIVA_DLL="/path/to/KSP/GameData/FreeIva/Plugins/FreeIva.dll" \
MK33_DOTNET="/path/to/dotnet" bash build.sh
```

`build.sh` invokes the SDK C# compiler directly against the KSP framework libraries
and requires no NuGet restore. `Mk33FreeIVA.csproj` is supplied for IDE use on a
machine with the .NET Framework 4.8 targeting pack. Both produce the same source
assembly API; the shipped DLL is built using `build.sh`.

## Load order and scope

Place `Mk33FreeIvaGeometry` directly in an `INTERNAL`, before
`InternalModuleFreeIva`. Repeated `sourceTransform` values select fixed MeshFilters.
Native FreeIVA `Cut` blocks belong inside this helper. It cuts the installed visual
meshes first, then creates non-convex, non-trigger layer-16 MeshColliders from the
result. No art or triangle data is embedded in the plugin.

Set `shellColliderName = Mk33Shell` in the following `InternalModuleFreeIva`.
Additional independently authored corridor colliders can be named separately.
Do not add later FreeIVA `Cut`, automatic hatch cutouts, or moving-door geometry to
these source lists: late cuts would invalidate the collider snapshot, and a static
copy of a moving door would block an open hatch. Ordinary hatch door colliders
remain owned by `FreeIvaHatch`.

The marker on the generated root is cloned with the INTERNAL prefab and suppresses
repeated processing. Full transform matrices bake original mesh vertices into
internal-local space, preserving non-uniform scale. No source renderer layer,
exterior collider, part resource, or kerbal collision setting is changed.

The helper validates names and configuration before cutting, rejects pre-existing
solid source colliders, and logs `[Mk33FreeIVA]` errors for failures. A failed
INTERNAL must not be used for FreeIVA until corrected; errors are not treated as a
successful compatibility result. FreeIVA's cutter internally catches some cutter
exceptions, so consult both `[FreeIva]` and `[Mk33FreeIVA]` messages in KSP.log.

`Mk33FreeIvaHatch` is a thin subclass of the native `FreeIvaHatch` for existing
doors configured directly under INTERNAL. It reads `dockingPortNodeName`,
`requireDeploy`, `tubeExtent`, and `hideDoorWhenConnected`, which native FreeIVA
normally reads via a separate per-PROP HatchConfig. All door behavior remains
native. `position`, `rotation`, `doorTransformName`, `DoorCollider`, and
`HandleCollider` retain their native meanings. `tubeExtent` is accepted for API
completeness but FreeIVA 0.2.20.2 does not use it to calculate tube length.

Compilation verifies API compatibility only. Mesh cooking, module load order,
repeated IVA entry, collision motion, seats and all bidirectional traversal tests
still require the actual KSP runtime.

Code license: GPL-2.0-or-later. Runtime dependency FreeIVA code is GPLv2; its art is
not redistributed. Mk-33 installed art remains subject to its own rights.

Build reference source:
https://github.com/KSPModdingLibs/KSPLibs (KSP-1.12.5.zip, stripped method bodies).
FreeIVA source and API:
https://github.com/FirstPersonKSP/FreeIva/tree/0.2.20.2
