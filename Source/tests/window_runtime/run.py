#!/usr/bin/env python3
"""Run the exact production window helper with dependency doubles, not Unity.
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
SOURCE=ROOT/'Source'/'Mk33FreeIvaWindowMask.cs'
REPORT=ROOT/'Tests'/'window-runtime-checks.json'
dotnet=os.environ.get('MK33_DOTNET','dotnet')
with tempfile.TemporaryDirectory(prefix='mk33-window-harness-') as temporary:
    temporary=Path(temporary)
    environment=dict(os.environ,DOTNET_CLI_HOME=str(temporary/'cli-home'),DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',DOTNET_NOLOGO='1')
    records=subprocess.check_output([dotnet,'--list-sdks'],text=True,env=environment).strip().splitlines()
    version,base=records[-1].split(' [',1)
    sdk=Path(base.rstrip(']'))/version
    installation=sdk.parent.parent
    references=sorted((installation/'packs'/'Microsoft.NETCore.App.Ref').glob('8.*/ref/net8.0'))[-1]
    runtime=sorted((installation/'shared'/'Microsoft.NETCore.App').glob('8.*'))[-1].name
    output=temporary/'window_runtime.dll'
    subprocess.run([dotnet,str(sdk/'Roslyn'/'bincore'/'csc.dll'),'-nologo','-target:exe','-noconfig','-nostdlib+','-warnaserror+','-out:'+str(output),*['-reference:'+str(p) for p in sorted(references.glob('*.dll'))],str(HERE/'Stubs.cs'),str(HERE/'Program.cs'),str(SOURCE)],check=True,env=environment)
    (temporary/'window_runtime.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'tfm':'net8.0','framework':{'name':'Microsoft.NETCore.App','version':runtime}}}))
    subprocess.run([dotnet,str(output),str(REPORT)],check=True,env=environment)
result=json.loads(REPORT.read_text())
result['production_source']='Source/Mk33FreeIvaWindowMask.cs'
result['production_source_sha256']=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
result['scope_limitations']=['Executes exact production helper with dependency doubles; does not execute KSP/Unity, GPU shaders, real camera compositing, prefab serialization, native FreeIVA OnLoad, or ModuleManager.','Geometry source checks and actual API compilation are separate.','Render-queue hazard and recovery scenarios establish code behavior, not the cause of an unrecorded user GPU frame.']
REPORT.write_text(json.dumps(result,indent=2)+'\n')
