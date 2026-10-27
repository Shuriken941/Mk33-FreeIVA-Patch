"""Validate current exported render data and texture references. GPL-2.0-or-later.
No KSP/Unity rendering or physics is executed.
"""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'Source/source_checks'))
from mu import Mu

def walk(o):
    yield o
    for c in o.children:yield from walk(c)

report={'in_game_tested':False,'models':{}}
for path in sorted((ROOT/'Models').glob('*.mu')):
    m=Mu().read(str(path));count=0
    for o in walk(m.obj):
        if not hasattr(o,'renderer'):continue
        mesh=o.shared_mesh;n=len(mesh.verts)
        assert n and np.isfinite(mesh.verts).all(),(path.name,o.transform.name)
        assert len(mesh.normals)==n and len(mesh.uvs)==n,(path.name,o.transform.name,'normals or UV count')
        assert np.isfinite(mesh.normals).all() and np.isfinite(mesh.uvs).all()
        for sm in mesh.submeshes:
            faces=np.array(sm);assert faces.shape[1]==3 and faces.min()>=0 and faces.max()<n
        assert o.renderer.materials
        for index in o.renderer.materials:
            assert 0<=index<len(m.materials)
            mat=m.materials[index];assert mat.shaderName in ['KSP/Diffuse','KSP/Unlit']
            for tex in mat.textureProperties.values():
                assert 0<=tex.index<len(m.textures)
                name=m.textures[tex.index].name
                assert (ROOT/'Models'/(name+'.png')).is_file(),name
        count+=1
    report['models'][path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rendered_mesh_count':count,'uv_normals_materials_textures_valid':True}
(ROOT/'Tests/visual-package-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
