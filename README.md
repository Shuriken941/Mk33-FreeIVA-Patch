# Mk33 FreeIVA Patch

**FreeIVA compatibility patch for the [Mk-33](https://github.com/Angel-125/Mk-33) spaceplane in Kerbal Space Program 1.**

[**Download the latest version**](https://github.com/Shuriken941/Mk33-FreeIVA-Patch/releases/latest) · [All releases](https://github.com/Shuriken941/Mk33-FreeIVA-Patch/releases) · [Report an issue](https://github.com/Shuriken941/Mk33-FreeIVA-Patch/issues)

> **Current release: V0.3.5.** Core FreeIVA functionality is implemented. Some visual issues and a gravity-related ladder limitation remain.

[V0.3.5 changelog](CHANGELOG.md)

## Features

- Walk between the Mk-33 cockpit, Krew Module and airlock interiors.
- Traverse compatible docked vessels through the Krew Module docking tube and external airlock.
- Use the Krew Module upper EVA hatch and the lower-deck cockpit EVA exit.
- Improved connecting corridors, hatch textures and interior depth masking.
- Probe Core docking functionality restored after an issue in an earlier release.

## Installation

1. Install **Kerbal Space Program 1**, the original [Mk-33](https://github.com/Angel-125/Mk-33), [FreeIVA](https://github.com/FirstPersonKSP/FreeIva) and their required dependencies, including ModuleManager.
2. Download the ZIP under **Assets** on the [latest release page](https://github.com/Shuriken941/Mk33-FreeIVA-Patch/releases/latest).
3. Extract the release ZIP and merge its `GameData` folder into your KSP installation's `GameData` folder. Keep the ZIP's original folder structure.
4. Restart the game and test with a compatible Mk-33 craft.

**Do not install by copying this repository's development folders into `GameData`.** Use the packaged release ZIP instead.

## Known limitations (V0.3.5)

- The ladder connecting the cockpit to the passage toward the airlock and lower deck cannot currently be climbed under gravity.
- Some hatch textures are incorrectly oriented.
- Minor visual imperfections remain.

Please include your KSP, Mk-33 and FreeIVA versions, steps to reproduce, and `KSP.log` when [reporting bugs](https://github.com/Shuriken941/Mk33-FreeIVA-Patch/issues).

## Repository structure

| Path | Contents |
| --- | --- |
| [Source](Source/) | C# helper, build scripts and asset/config generators |
| [Models](Models/) | Patch-authored model and texture files |
| [Patches](Patches/) | ModuleManager configuration |
| [Plugins](Plugins/) | Compiled helper DLL |
| [Tests](Tests/) | Development tests, static checks and test craft |
| [LICENSES](LICENSES/) | License texts |
| [THIRD_PARTY.md](THIRD_PARTY.md) | Third-party credits and redistribution notes |
| [docs](docs/) | Archived V0.1 development documentation |

> **Source version:** The `main` branch now contains the sources and assets from the **V0.3.5 release**. For installation use the release ZIP. The original Ukrainian release instructions are at [docs/README-v0.3.5-uk.md](docs/README-v0.3.5-uk.md).

## Credits and licenses

- **Original Mk-33:** [Angel-125](https://github.com/Angel-125/Mk-33)
- **FreeIVA:** [FirstPersonKSP contributors](https://github.com/FirstPersonKSP/FreeIva)

This is an **independent, unofficial compatibility patch**; it is not an official release of Mk-33 or FreeIVA. See [THIRD_PARTY.md](THIRD_PARTY.md) and [LICENSES](LICENSES/) for attribution and license information.

Thanks to everyone following the project and sharing feedback!
