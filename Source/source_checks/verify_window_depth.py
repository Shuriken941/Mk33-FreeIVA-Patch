#!/usr/bin/env python3
"""Source-level depth ordering and installed-window coverage audit.

This is a small depth-buffer model and geometric audit, NOT a GPU/KSP test.
SPDX-License-Identifier: GPL-2.0-or-later.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
from inspect_mu import nodes

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Source'))
from verify_package import parse, value


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def depth_composition(mask_queue, fragments, through_window=True):
    """ColorMask0 writes depth while retaining prior external-camera colour."""
    color='external world'
    depth=float('inf')
    events=list(fragments)
    if through_window:
        # Native shader's positive polygon offset keeps original glass drawable.
        events.append((mask_queue,2.0001,None))
    for _,z,colour in sorted(events,key=lambda event:event[0]):
        if z<=depth:
            depth=z
            if colour is not None:
                color=colour
    return color


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--freeiva',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True)
    args=parser.parse_args()
    native=args.freeiva/'FreeIva/InternalModules/InternalModuleFreeIva.cs'
    shader=args.freeiva/'FreeIva_Unity/Assets/ForBundle/DepthMask_Culling.shader'
    native_text=native.read_text(encoding='utf-8-sig')
    shader_text=shader.read_text(encoding='utf-8-sig')
    helper=ROOT/'Source/Mk33FreeIvaWindowMask.cs'
    helper_text=helper.read_text()
    assert 'CURRENT_PART_RENDER_QUEUE = 999;' in native_text
    assert 'WINDOW_RENDER_QUEUE = 1999;' in native_text
    assert 'OPAQUE_RENDER_QUEUE = 2000;' in native_text
    assert '"Queue" = "Background"' in shader_text
    for statement in ['ColorMask 0','ZWrite On','ZTest LEqual','Cull Back']:
        assert statement in shader_text,statement
    assert 'CURRENT_PART_RENDER_QUEUE - 1' in helper_text
    assert 'new Material(shader)' in helper_text
    assert 'native.internalDepthMask = maskTransform' in helper_text
    roots=parse((ROOT/'Patches/Mk33_FreeIVA.cfg').read_text())
    models={'wbiMk33CockpitSpace':'cockpitIVA','wbiMk33CrewModuleSpace':'crewModuleIVA','wbiMk33ControlCabSpace':'controlCabIVA'}
    geometry=[]
    for internal,model in models.items():
        config=next(n for n in roots if n['type'].startswith('@INTERNAL['+internal+']'))
        modules=[n for n in config['nodes'] if n['type']=='MODULE']
        wm=next(n for n in modules if value(n,'name')=='Mk33FreeIvaWindowMask')
        im=next(n for n in modules if value(n,'name')=='InternalModuleFreeIva')
        assert modules.index(wm)<modules.index(im)
        assert value(im,'internalDepthMaskName')=='Mk33WindowDepthMask'
        assert value(im,'externalDepthMaskFile')
        assert value(im,'windowName')=='windows' and value(wm,'sourceTransform')=='windows'
        path=args.assets/(model+'.mu')
        sources=[n for n in nodes(path) if n['name']=='windows']
        assert len(sources)==1
        source=sources[0]
        vertices=source['verts']
        # The mu reader returns triangle tuples, not flat indices.
        faces=np.array([tri for sub in source['mesh'].submeshes for tri in sub],dtype=int)
        assert faces.ndim==2 and faces.shape[1]==3 and len(faces)>0
        assert np.isfinite(vertices).all() and faces.min()>=0 and faces.max()<len(vertices)
        triangles=vertices[faces]
        normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        areas=np.linalg.norm(normals,axis=1)*.5
        assert np.all(areas>1e-10),model
        mask=np.concatenate([faces,faces[:,[0,2,1]]])
        mask_triangles=vertices[mask]
        mask_normals=np.cross(mask_triangles[:,1]-mask_triangles[:,0],mask_triangles[:,2]-mask_triangles[:,0])
        assert np.allclose(mask_normals[:len(faces)],-mask_normals[len(faces):])
        lower,upper=vertices.min(0),vertices.max(0)
        apertures=[]
        for m in modules:
            if value(m,'name') not in ('Mk33FreeIvaPressureHatch','Mk33FreeIvaHatch'):
                continue
            position=value(m,'position')
            if position is None:
                continue
            center=np.array([float(x) for x in position.split(',')])
            distance=float(np.linalg.norm(np.maximum(np.maximum(lower-center,center-upper),0)))
            # Conservative AABB-to-aperture sphere separation; all existing
            # and newly configured hatch centers stay outside the glass mask.
            assert distance>.525,(model,value(m,'hatchId',value(m,'doorTransformName')),distance)
            apertures.append({'hatch':value(m,'hatchId',value(m,'doorTransformName')),'minimum_distance_from_window_bounds_m':distance,'radius_test_m':.525})
        geometry.append({'internal':internal,'source_model':model+'.mu','source_sha256':digest(path),'source_triangles':len(faces),'mask_triangles':len(mask),'source_vertices':len(vertices),'source_surface_area_m2':float(areas.sum()),'both_windings_verified':True,'all_configured_hatch_apertures_clear':apertures})
    old_leak=depth_composition(1000,[(999,3,'earlier IVA')])
    assert old_leak=='earlier IVA'
    cases=[
        ('Other module behind the window',[(2000,3,'other IVA')],True,'external world'),
        ('An IVA already promoted to queue999 behind the window',[(999,3,'earlier IVA')],True,'external world'),
        ('Own interior in front of the window',[(999,1,'own interior'),(2000,3,'other IVA')],True,'own interior'),
        ('Open hatch has no window mask',[(2000,3,'connected interior')],False,'connected interior'),
        ('Clear view retains the already-rendered external world',[],True,'external world'),
    ]
    compositor=[]
    for name,fragments,window,expected in cases:
        actual=depth_composition(998,fragments,window)
        assert actual==expected,(name,actual,expected)
        compositor.append({'case':name,'expected_color':expected,'actual_color':actual,'pass':True})
    result={'in_game_tested':False,'gpu_tested':False,'production_source_sha256':digest(helper),'native_freeiva_source_sha256':digest(native),'native_depth_shader_source_sha256':digest(shader),'native_occupied_opaque_queue':999,'native_hull_depth_queue':1000,'window_only_depth_queue':998,'native_glass_queue':1999,'native_other_opaque_queue':2000,'native_depth_only_shader_statements_verified':['ColorMask 0','ZWrite On','ZTest LEqual','Cull Back'],'geometry':geometry,'software_depth_composition':compositor,'negative_control_native1000_after_earlier999':{'result':old_leak,'leak_detected':True},'scope_limitations':['Software depth-buffer model validates ordering logic; it does not execute Unity shader compilation, real cameras, Deferred/Shabby, GPU depth precision, or third-party rendering.','Installed source window mesh coverage and hatch separation are validated without copying original art into the package.','The ordering regression is a demonstrated hazard, not proof of the root cause of the user\'s earlier screenshot.','KSP gameplay must confirm external-world visibility, seated/unbuckled view, camera transitions and all windows in the user\'s renderer configuration.']}
    out=ROOT/'Tests/window-depth-checks.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 3 installed window meshes, all configured apertures, native shader/queue contract and 5 software composition cases; native1000 negative control leaks as expected.')
    print(out)

if __name__=='__main__':
    main()
