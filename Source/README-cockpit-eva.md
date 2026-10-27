# Lower-deck cockpit EVA (V0.3.5)

The large original `EXIT / UNLOCK / EMERGENCY SLIDE` door on the lower deck
now has a native FreeIVA EVA interaction. Aim at its UNLOCK handle area and use
the normal FreeIVA hatch interaction. FreeIVA performs stock EVA immediately
through the original side exit, `Airlock,0`. KSP's EVA permissions, tourist
restriction and exterior obstruction checks still apply. An obstructing part
outside the door can therefore prevent exit.

This action does not open a walkable hole into vacuum. The original leaf and
wall stay solid and retain their original appearance, as appropriate for the
native immediate-EVA interaction. No door-opening animation is added.

`Mk33CockpitLowerEvaHandle` uses the existing original-hatch adapter. It detaches
only the three original UNLOCK handle pieces (104 triangles) from the installed
`Dashboard` mesh into a lifecycle-safe interaction object. It preserves the
original materials, UVs and world pose. The original leaf/wall remains in
`Dashboard` and its existing physical shell. No cockpit cut, corridor, old hatch
binding or external part model is changed. The interaction box is 0.20 x 0.32 x
0.32 metres, making the handle area easier to target than its visible geometry.

The first original exterior `Airlock` transform is tagged `Airlock` and has a
trigger collider. Its part-local position is approximately
`(-3.040660, 2.236998, 0.630000)`; the second Airlock is the aft exit and is not
used by this new interaction.

Validation:

```sh
python Source/source_checks/verify_cockpit_eva.py \
  --assets /path/to/WildBlueIndustries/Mk-33/Parts/SharedAssets \
  --freeiva-source /path/to/FreeIva
```

Optional `--baseline /path/to/v034/GameData/Mk33FreeIVA` also proves all existing
cockpit hatch settings and cuts are unchanged. The report is
`Tests/cockpit-eva-checks.json`. It checks the selector/tag/trigger, exact handle
extraction, disjoint handle/leaf components, preservation of all source triangles,
and 289 rays across the retained leaf. It also audits the exact native EVA
source when supplied. It does not execute KSP spawning or Unity/PhysX.

No original Mk-33 art is redistributed in this patch.
