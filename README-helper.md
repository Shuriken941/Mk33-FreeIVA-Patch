# Mk33FreeIVA helper source

The helper is compiled against the public API of **KSP 1.12.5** and **FreeIVA
0.2.20.2**, targeting the game's .NET Framework/Mono runtime. No KSP, Unity,
FreeIVA or Mk-33 reference binary is included in the installable package.

## Why a helper is necessary

FreeIVA's `Cut` edits a `MeshFilter`; it does not rebuild a separate
`MeshCollider`. The original Mk-33 IVA meshes have no usable walking colliders.
This helper first applies FreeIVA's own cuts, then builds collision-only meshes
from the already-cut **installed** Mk-33 geometry. Consequently the visible
aperture and the generated collision aperture use the same vertex/triangle data.
No original art data is stored in this DLL or in this source.

Each collider is nonconvex and lies on the FreeIVA kerbal collision layer (16).
The complete source-transform matrix is baked into internal-local coordinates,
including negative or nonuniform scale. Original visual objects keep their
transforms, materials and layers. Original seats, walls and equipment remain
physical when listed as sources. No character collision, external part
collider, aerodynamics or strength setting is changed.

## Configuration and loading order

Place one `MODULE { name = Mk33FreeIvaGeometry ... }` directly in an `INTERNAL`,
**before** `InternalModuleFreeIva`. Repeat `sourceTransform = exactName` for each
fixed mesh, and place native FreeIVA `Cut` blocks inside that helper module.
`InternalModuleFreeIva` must subsequently use `shellColliderName = Mk33Shell`;
additional separately authored corridor shells can have extra values.

Use explicit `position`, `rotation`, `scale` in procedural cuts. A
`ProceduralCylinder` also requires positive `radius`, positive `height` and
8–128 `slices`. Its native FreeIVA axis is +Z, starting at `position` and ending
at `position + rotated (0, 0, height)`. Mesh cut tools must exist as named
MeshFilters. Names can use a zero-based `name,index` occurrence selector.

Do **not** add later `InternalModuleFreeIva.Cut`, prop auto-cutting or
`HatchConfig.cutoutTargetTransformName` operations on these sources: a later
visual-only cut would invalidate the collider snapshot. Do not list a moving
door such as `crewDoor` among fixed sources. Its `DoorCollider` belongs to the
door controlled by FreeIVA and must disappear/move with it.

`Mk33FreeIvaHatch` inherits all native FreeIVA hatch behavior. Its only adapter
work is reading `dockingPortNodeName`, `requireDeploy`, `tubeExtent` and
`hideDoorWhenConnected` from a direct-INTERNAL module (native `HatchConfig`
accepts these only within a PROP). It also normalizes a missing `attachNodeId`
to an empty string. Other fields and `DoorCollider`/`HandleCollider` are native.
It does not create connections, teleport kerbals or bypass deployment checks.
`tubeExtent` is accepted for API compatibility; FreeIVA 0.2.20.2 actually scales
tubes using the connected hatch positions.

The `Mk33ColliderMarker` component is cloned with the INTERNAL prefab and avoids
duplicate work on repeated loading. Missing sources, malformed cuts, conflicting
shells or existing solid source colliders produce an explicit `[Mk33FreeIVA]`
error. An incomplete result is not marked complete. A failure is **not** a
supported flight state; correct the logged error before using that interior.
The helper does not globally remove pre-existing colliders to hide a failure.

## Building

Install a .NET SDK (the delivered DLL was built with SDK 8.0.426). Set:

```sh
export KSP_MANAGED="/path/to/KSP/KSP_x64_Data/Managed"
export FREEIVA_DLL="/path/to/KSP/GameData/FreeIva/Plugins/FreeIva.dll"
bash build.sh
```

Alternatively set `MK33_DOTNET` to the absolute path of the SDK executable.
`build.sh` invokes Roslyn directly, uses the game's own `mscorlib`, `System`,
`System.Core`, `Assembly-CSharp`, `UnityEngine`, `UnityEngine.CoreModule` and
`UnityEngine.PhysicsModule` as references, and writes only
`../Plugins/Mk33FreeIVA.dll`. No NuGet restore is required. The accompanying
`.csproj` is supplied for IDE use and requires the same two reference variables.

The build here used the stripped, build-only KSP reference set from
<https://github.com/KSPModdingLibs/KSPLibs> (`KSP-1.12.5.zip`) and the official
FreeIVA 0.2.20.2 release. Reference DLLs are not game executables and cannot run
KSP physics tests.

## Validation limits and license

Compilation against the actual API passed with warnings treated as errors.
This validates type/method signatures, not the KSP loader, Unity mesh cooking,
in-game collider orientation, seat egress or bidirectional hatch traversal.
Those must be tested in KSP 1.12.5 using the supplied test procedure.

This helper source and DLL are licensed **GPL-2.0-or-later**. FreeIVA source
is GPL-2.0-or-later; its art and Mk-33 art retain their respective rights.
