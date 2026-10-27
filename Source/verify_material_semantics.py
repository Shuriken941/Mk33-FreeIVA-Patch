"""Confirm material-table compaction preserves model semantics; MIT license.

Python 3 standard library; --baseline points at an older Mk33FreeIVA folder.
This geometry comparison complements the independent sequential KSPCF reader.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE/'source_checks'))
from mu import Mu

def freeze(value):
    if isinstance(value,(str,int,float,bool,type(None))):return value
    if isinstance(value,(list,tuple)):return [freeze(x) for x in value]
    if isinstance(value,dict):return {k:freeze(v) for k,v in value.items()}
    return {'type':type(value).__name__,**{k:freeze(v) for k,v in vars(value).items()}}

def material(mu,index):
    m=mu.materials[index]
    result={k:freeze(v) for k,v in vars(m).items() if k!='textureProperties'}
    result['textureProperties']={}
    for key,texture in m.textureProperties.items():
        values={k:freeze(v) for k,v in vars(texture).items() if k!='index'}
        values['texture']=freeze(mu.textures[texture.index])
        result['textureProperties'][key]=values
    return result

def node(mu,o):
    result={k:freeze(v) for k,v in vars(o).items() if k not in ('children','components','renderer')}
    if hasattr(o,'renderer'):
        result['renderer']={k:freeze(v) for k,v in vars(o.renderer).items() if k!='materials'}
        result['renderer']['materials']=[material(mu,i) for i in o.renderer.materials]
    result['children']=[node(mu,c) for c in o.children]
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True);args=ap.parse_args()
    result={'ksp_unity_executed':False,'method':'Compare decoded complete transforms, collider and renderer meshes, normals, UVs, light and trigger properties; renderer material references resolve to material names/shaders/properties and actual texture names before comparison.','models':{}}
    for path in sorted((ROOT/'Models').glob('*.mu')):
        before=args.baseline/'Models'/path.name
        old,new=Mu().read(str(before)),Mu().read(str(path))
        assert node(old,old.obj)==node(new,new.obj),path.name
        result['models'][path.stem]={'geometry_hierarchy_collision_lighting_unchanged':True,'renderer_material_and_texture_mapping_unchanged':True,'material_count_before':len(old.materials),'material_count_after':len(new.materials),'texture_count_before':len(old.textures),'texture_count_after':len(new.textures),'old_sha256':hashlib.sha256(before.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (ROOT/'Tests'/'material-export-geometry-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
