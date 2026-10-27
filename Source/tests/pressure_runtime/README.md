# Pressure-hatch and initialization checks

Run with Python 3 and a .NET 8 SDK:

```sh
MK33_DOTNET=/path/to/dotnet python run.py
```

The runner compiles the entire current production `Mk33FreeIvaPressureHatch.cs`
and `Mk33FreeIvaGeometry.cs` files directly. It does not extract or reimplement
production lifecycle methods. The executable runs 101 scenarios covering pressure
state, connection checks, generated geometry, initialization order, native cache
readiness and ownership of walking blocks. The report in
`Tests/pressure-runtime-checks.json` records both source hashes.

The added imported-shell cases begin with `MeshCollider.convex=true`, matching
the assignment in the exact KSPCF 1.41.1 parser used in the supplied KSP log.
They check normalization before geometry/authored-shell readiness and before
native loading of the Krew and Nose dynamic tubes. Invalid layer, trigger,
disabled, empty or missing sources still fail; unrelated convex colliders and
original box seals remain unchanged. The native hatch double records tube state
at entry to `OnLoad` to check ordering.

`Stubs.cs` supplies dependency doubles. The native hatch double implements only
the documented state, blocked-deployment, EVA and registration behavior required
to exercise the custom code. It can restrict transform lookup to a modelled PROP
wrapper, omit native reparenting, or fail native initialization after a partial
state change. Renderer doubles include skinned and nested artwork. Geometry
matrix doubles support the no-cut shell cases used here. Any `MeshCutter`
create/cut request deliberately throws: native mesh cutting is not tested.

`lifecycle-baseline.json` records execution of the prior 0.3.1 sources: an Awake
before OnLoad disabled unbuckling in pressure, original-door and authored-shell
modules, and successful later loading did not restore it. That is a deterministic
source-level reproduction with dependency doubles, not a KSP gameplay recording.

`forced-convex-baseline.json` records execution of the prior 0.3.2 sources with
that imported-convex assignment: the corridor/authored shell was rejected and
walking stayed blocked. It also records the exact parser source hash and the
matching error in the supplied user log. The parser assignment is mirrored by
these tests; this harness does not execute KSPCF's parser itself.

These checks do not execute KSP's asset/INTERNAL loader, ModuleManager, native
connection-discovery coroutines, Unity shader rendering, or PhysX. Simulated
loader and callback orders do not prove which order occurred in a particular
KSP session. Passing cannot establish actual movement or mesh/collider cooking.
The production build separately compiles against the actual KSP/Unity/FreeIVA API.

Compilation and execution happen in a temporary directory. No NuGet download or
game installation is needed.

The central AIRLOCK regressions cover extracting the original door/handle
triangles with preserved artwork, exact signature and no-source-mutation
failure guards, plus automatic opening only for deployed physical docking with
complete own/peer shells and resealing after a disconnect.
