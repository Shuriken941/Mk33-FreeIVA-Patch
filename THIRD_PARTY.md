# Sources, attribution and distribution scope

- **Mk-33, Angel-125 / Michael Billard**: source snapshot
  `fff40f9f602b72f5bad2f7ec888985886d163f98`, version metadata 1.3.3.0.
  <https://github.com/Angel-125/Mk-33/tree/fff40f9f602b72f5bad2f7ec888985886d163f98>
  The upstream README and distributed Readme.txt state that art assets are
  **All Rights Reserved**, while configuration/source files are GPLv3.
  No Mk-33 `.mu`, texture, artwork or original craft file is redistributed.
  Runtime references read the user's installed models. New connector surfaces
  and functional hatches are authored from parametric primitives; they contain
  no copied Mk-33 triangles or texture pixels.
- **FreeIVA, FirstPersonKSP contributors**: runtime/build target 0.2.20.2,
  <https://github.com/FirstPersonKSP/FreeIva/releases/tag/0.2.20.2>.
  Code GPL-2.0-or-later; upstream model, texture and sound assets generally
  retain All Rights Reserved unless stated otherwise. No FreeIVA binary or
  artwork is redistributed. The helper links to the installed native API.
  <https://github.com/FirstPersonKSP/FreeIva/blob/0.2.20.2/FreeIva/MeshCutter.cs>
  <https://github.com/FirstPersonKSP/FreeIva/blob/0.2.20.2/FreeIva/InternalModules/Hatches/Hatch.cs>
  <https://github.com/FirstPersonKSP/FreeIva/wiki/Configuring-a-part-for-FreeIva>
  <https://github.com/FirstPersonKSP/FreeIva/wiki/CFG-documentation>
  Native examples inspected include ERS, Pathfinder, Heisenberg and Buffalo2
  patches. The incomplete Mk-33 configuration in upstream main was researched,
  but its art is not included and its seat-deletion rules are not used.
- **KSPModdingLibs / KSPLibs**: stripped, build-only KSP 1.12.5 reference
  assemblies from <https://github.com/KSPModdingLibs/KSPLibs> were used to
  compile the helper. They have no game implementation and cannot run physics.
  No KSP or Unity assembly is included in this package.
- **taniwha / io_object_mu**: GPL-2.0-or-later `.mu` reader used during source
  geometry research: <https://github.com/taniwha/io_object_mu/blob/master/mu.py>.
  Its license applies if supplied with the optional source-check tooling.

Our helper, patch and configuration generators are GPL-2.0-or-later; see
`LICENSES/GPL-2.0.txt`. Our original procedural asset code, generated assets
and corridor verifier are MIT; see `LICENSES/MIT-assets.txt`. Reports and test
instructions are provided with the package under GPL-2.0-or-later.

This is an independent compatibility patch, not an official release of either
Mk-33 or FreeIVA. Upstream ownership and trademarks remain with their authors.
