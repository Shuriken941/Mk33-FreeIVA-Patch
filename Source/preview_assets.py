"""Render exported authored .mu art for review, not a KSP gameplay screenshot.
SPDX-License-Identifier: MIT. blender -b --python preview_assets.py -- output.png
"""
from pathlib import Path
import sys,os
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source_checks'))
from mu import Mu
ROOT=HERE.parent
OUT=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else ROOT/'Tests/corridor-preview.png'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
model=sys.argv[sys.argv.index('--')+2] if '--' in sys.argv and len(sys.argv)>sys.argv.index('--')+2 else 'CockpitCorridor'
mu=Mu().read(str(ROOT/'Models'/('CockpitCorridor.mu' if model=='CockpitShaft' else model+'.mu')))
materials=[]
for source in mu.materials:
    mat=bpy.data.materials.new(source.name);mat.use_nodes=True
    tree=mat.node_tree;tree.nodes.clear()
    out=tree.nodes.new('ShaderNodeOutputMaterial')
    shader=tree.nodes.new('ShaderNodeEmission' if 'Unlit' in source.shaderName else 'ShaderNodeBsdfDiffuse')
    tex=tree.nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(ROOT/'Models'/(mu.textures[source.textureProperties['_MainTex'].index].name+'.png')))
    tree.links.new(tex.outputs['Color'],shader.inputs['Color'])
    tree.links.new(shader.outputs[0],out.inputs[0]);materials.append(mat)
def visit(o,parent=None):
    empty=bpy.data.objects.new(o.transform.name,None);bpy.context.collection.objects.link(empty)
    empty.parent=parent;empty.location=o.transform.localPosition
    empty.rotation_mode='QUATERNION';empty.rotation_quaternion=o.transform.localRotation;empty.scale=o.transform.localScale
    if hasattr(o,'shared_mesh'):
        mesh=bpy.data.meshes.new(o.transform.name+'Mesh')
        mesh.from_pydata(o.shared_mesh.verts,[],sum(o.shared_mesh.submeshes,[]));mesh.update()
        obj=bpy.data.objects.new(o.transform.name+'Render',mesh);bpy.context.collection.objects.link(obj);obj.parent=empty
        mesh.materials.append(materials[o.renderer.materials[0]])
        uv=mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            for i in poly.loop_indices:uv.data[i].uv=o.shared_mesh.uvs[mesh.loops[i].vertex_index]
    if hasattr(o,'light'):
        data=bpy.data.lights.new(o.transform.name,'POINT');data.energy=o.light.intensity*28
        data.color=o.light.color[:3];data.shadow_soft_size=.09
        obj=bpy.data.objects.new(o.transform.name+'Light',data);bpy.context.collection.objects.link(obj);obj.parent=empty
    for child in o.children:visit(child,empty)
visit(mu.obj)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=False
scene.world.color=(.025,.025,.025)
scene.view_settings.view_transform='AgX'
data=bpy.data.cameras.new('camera');cam=bpy.data.objects.new('camera',data);bpy.context.collection.objects.link(cam)
# Blender parser converts Unity X,Y,Z to X,Z,Y; camera is inside the entry.
cam.location=(0,-.14,1.055827) if model=='KrewDockPassage' else (0,-1.43,-.565)
direction=Vector((0,.61551148,1.30) if model=='KrewDockPassage' else (0,1.9,-.10))-cam.location
if model=='CockpitShaft':
    cam.location=(0,.02,1.48);direction=Vector((0,.9,.82))-cam.location
cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler();data.lens=17;data.clip_start=.01
scene.camera=cam;scene.render.resolution_x=1280;scene.render.resolution_y=800;scene.render.resolution_percentage=100
if model=='KrewDockPassage':scene.render.resolution_percentage=50;scene.cycles.samples=16
if os.environ.get('MK33_PREVIEW_FAST')=='1':scene.render.resolution_percentage=50;scene.cycles.samples=16
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT);OUT.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.render.render(write_still=True)
