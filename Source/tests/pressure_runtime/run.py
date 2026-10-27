#!/usr/bin/env python3
"""Execute actual hatch C# with small dependency doubles, not a KSP simulation.
SPDX-License-Identifier: GPL-2.0-or-later.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'Source'/'Mk33FreeIvaPressureHatch.cs'
REPORT=ROOT/'Tests'/'pressure-runtime-checks.json'
dotnet=os.environ.get('MK33_DOTNET','dotnet')
with tempfile.TemporaryDirectory(prefix='mk33-pressure-harness-') as temporary:
    temporary=Path(temporary)
    environment=dict(os.environ, DOTNET_CLI_HOME=str(temporary/'cli-home'), DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_NOLOGO='1')
    sdk_records=subprocess.check_output([dotnet,'--list-sdks'],text=True,env=environment).strip().splitlines()
    sdk_version,sdk_base=sdk_records[-1].split(' [',1)
    sdk=Path(sdk_base.rstrip(']'))/sdk_version
    installation=sdk.parent.parent
    reference_packs=sorted((installation/'packs'/'Microsoft.NETCore.App.Ref').glob('8.*/ref/net8.0'))
    if not reference_packs:
        raise RuntimeError('Install a .NET 8 SDK to run this offline dependency-double harness.')
    references=reference_packs[-1]
    runtime=sorted((installation/'shared'/'Microsoft.NETCore.App').glob('8.*'))[-1].name
    output=temporary/'pressure_runtime.dll'
    subprocess.run([dotnet,str(sdk/'Roslyn'/'bincore'/'csc.dll'),'-nologo','-target:exe','-noconfig','-nostdlib+',
        '-warnaserror+','-out:'+str(output),
        *['-reference:'+str(path) for path in sorted(references.glob('*.dll'))],
        str(HERE/'Stubs.cs'),str(HERE/'Program.cs'),str(SOURCE),str(ROOT/'Source'/'Mk33FreeIvaGeometry.cs')],
        check=True,env=environment)
    (temporary/'pressure_runtime.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'tfm':'net8.0','framework':{'name':'Microsoft.NETCore.App','version':runtime}}}))
    subprocess.run([dotnet,str(output),str(REPORT)],check=True,env=environment)
result=json.loads(REPORT.read_text())
result['production_source_sha256']=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
result['production_source']='Source/Mk33FreeIvaPressureHatch.cs'
result['original_adapter_source_sha256']=hashlib.sha256((ROOT/'Source'/'Mk33FreeIvaGeometry.cs').read_bytes()).hexdigest()
result['original_adapter_source']='Source/Mk33FreeIvaGeometry.cs (entire exact production file: geometry builder, original adapter, and readiness markers)'
result['previous_version_lifecycle_baseline']=json.loads((HERE/'lifecycle-baseline.json').read_text())
result['previous_version_forced_convex_baseline']=json.loads((HERE/'forced-convex-baseline.json').read_text())
result['scope_limitations']=['Dependency doubles do not execute Unity/PhysX collision, shader rendering, KSP asset loading, ModuleManager, or actual native FreeIVA connection discovery/coroutines.','The forced-convex regression mirrors the single assignment evidenced in the actual KSPCF 1.41.1 parser source; the native parser itself is not executed by this harness.','Simulated scoped-wrapper/no-reparent/renderer-variant conditions do not prove which loader state occurred in a particular KSP session.','Production sources are also compiled separately against actual KSP/Unity/FreeIVA API references by build.sh.']
result['geometry_source']='Source/Mk33FreeIvaGeometry.cs'
result['geometry_source_sha256']=result['original_adapter_source_sha256']
result['mesh_cutter_dependency_double']='Any native MeshCutter create/cut request deliberately throws; these checks exercise lifecycle/readiness and no-cut shell generation only.'
result['native_loader_dependency_shapes']=['hasModel=false with model-wide transform search','hasModel=true with transform search restricted to wrapper subtree','native door reparenting omitted','native Awake failure after partial open-state change','MeshRenderer, SkinnedMeshRenderer, nested multiple renderer nodes, and missing original art','Awake before OnLoad; Start before/after OnLoad; native per-model cache absent then ready; repeated lifecycle callbacks','Live ModuleFreeIva replacement/absence, configured false policy, multiple gate owners and owner destruction']
result['imported_shell_regression_shapes']=['KSPCF parser-forced convex=true before required-shell and authored-shell validation','Krew original-hatch and Nose pressure-hatch dynamic named tubes observed at the beginning of native OnLoad','Layer, trigger, enabled state, empty/missing mesh and missing named source remain rejected','All declared compound-shell colliders validated before any convex mutation; unrelated convex colliders and original BoxCollider seals preserved']
REPORT.write_text(json.dumps(result,indent=2)+'\n')
