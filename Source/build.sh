#!/usr/bin/env bash
set -euo pipefail

# KSP reference assemblies or your installed KSP_x64_Data/Managed directory.
: "${KSP_MANAGED:?Set KSP_MANAGED to the KSP 1.12.5 Managed directory}"
: "${FREEIVA_DLL:?Set FREEIVA_DLL to FreeIVA 0.2.20.2 Plugins/FreeIva.dll}"
MK33_DOTNET="${MK33_DOTNET:-dotnet}"
MK33_SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MK33_SDK_RECORD="$("$MK33_DOTNET" --list-sdks | tail -n 1)"
MK33_SDK_VERSION="${MK33_SDK_RECORD%% *}"
MK33_SDK_BASE="${MK33_SDK_RECORD#*[}"
MK33_SDK_BASE="${MK33_SDK_BASE%]}"
MK33_CSC="$MK33_SDK_BASE/$MK33_SDK_VERSION/Roslyn/bincore/csc.dll"
test -f "$MK33_CSC"
mkdir -p "$MK33_SOURCE_DIR/../Plugins"

MK33_REFS=()
for MK33_REF in mscorlib System System.Core Assembly-CSharp UnityEngine UnityEngine.CoreModule UnityEngine.PhysicsModule; do
    test -f "$KSP_MANAGED/$MK33_REF.dll"
    MK33_REFS+=("-reference:$KSP_MANAGED/$MK33_REF.dll")
done
test -f "$FREEIVA_DLL"
"$MK33_DOTNET" "$MK33_CSC" -nologo -target:library -nostdlib+ -noconfig \
    -langversion:7.3 -optimize+ -deterministic+ -debug- -warnaserror+ \
    "${MK33_REFS[@]}" "-reference:$FREEIVA_DLL" \
    "-out:$MK33_SOURCE_DIR/../Plugins/Mk33FreeIVA.dll" \
    "$MK33_SOURCE_DIR/Mk33FreeIvaGeometry.cs" \
    "$MK33_SOURCE_DIR/Mk33FreeIvaWindowMask.cs" \
    "$MK33_SOURCE_DIR/Mk33FreeIvaPressureHatch.cs"
