# 0.3.5

- Harden window-only depth masks, preserving native glass and FreeIVA camera modes.
- Replace corridor surface maps with original Mk33-style quilted wall, ribbed floor and light ceiling textures.
- Reuse the installed FreeIVA classic round hatch visual; retain existing physical seals and hide-on-open behavior.
- Bind the lower cockpit EXIT door UNLOCK handle to the original side EVA airlock. Native EVA leaves the exterior wall intact.
- Preserve 0.3.4 physical routes, docking configuration and collision geometry.

# 0.3.4

- Correct Krew docking route to the central AIRLOCK door embedded in cabinMesh.
- Preserve original installed door/handle artwork by extracting exactly 352 triangles before source cuts.
- Automatically hide the door only after a physical, deployed FreeIVA docking connection; restore on disconnect/retraction.
- Remove the outside dogleg and central roof seal; keep the original aft Krew-to-Airlock bridge.
- Restore the neighboring roof crewDoor as EVA-only Airlock,1 without a roof cut or docking corridor.
- Place the shaft lining and radius-0.39 sleeve within the original central shaft and native docking aperture.
- Keep original Probe Core, Krew and Shielded Docking Port native modules and deployment indices unchanged.

# 0.3.3

- Fix unused material-table entries that made three own .mu files fail in the user's KSPCommunityFixes 1.41.1 loader.
- Restore nonconvex collision for declared passage shells and docking sleeves before readiness validation, matching native FreeIVA shell setup.
- Remove patch-pass specifiers from the two authored INTERNAL definitions so ModuleManager can insert the nose/probe interiors.
- Add regression evidence tied to the supplied 0.3.2 log and exact loader version; keep closed-door and incomplete-shell protection.

# 0.3.2

- Defer readiness checks until flight initialization has completed; an early Awake no longer permanently disables unbuckling on the whole part.
- Wait for native FreeIVA registration before initializing each hatch and initialize it only once.
- Track and release only this patch's walking blockers after successful readiness checks; preserve configured unbuckling restrictions and keep failed passages sealed.
- Add regression coverage for callback ordering, delayed context/native registration, real failures and owned-block recovery.

# 0.3.1

- Fix original-door lookup/ownership assumptions during INTERNAL compilation and contain initialization errors instead of letting validation abort KSP loading.
- Create persistent original-door handles in code and add loader-context regression cases.
- Surface-mount corridor fixtures; move the lamp away from the open shaft ceiling; support and crop the access ladder.
- Add fitted light housings/diffusers and refresh panels/floor with calmer markings.

# 0.3.0

- Circular doors are generated directly in INTERNAL with visible opaque plate, hardware, primitive solid collider and explicit closed initialization.
- Added own/peer shell-readiness, real attachment-graph and deployment checks; connection loss closes doors. Missing seals or auxiliary shells prevent source cuts; incomplete geometry prevents local unbuckling.
- Original Krew AIRLOCK door now controls a sealed illuminated dogleg to the deployable docking port. Removed its EVA binding and sealed the former separate central entry.
- Added front lower Cockpit opening, independent Probe Core corridor and Docking Nose Cone IVA with native docking sleeve.
- Added assembly prerequisites, extra source/geometry checks and 25 exact-source behavior scenarios with dependency doubles.
- Static test craft now includes the Probe Core and Docking Nose Cone.

The 0.3.2 user log confirmed model-reader and ModuleManager errors addressed in 0.3.3. KSP/Unity runtime acceptance of the new release remains outstanding.
