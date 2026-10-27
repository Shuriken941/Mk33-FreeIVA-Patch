"""Emit compact .mu material/texture references; SPDX-License-Identifier: MIT.

KSPCommunityFixes 1.41.1 allocates material dummies from renderer references,
then reads the declared material table into that exact array. An unused trailing
material definition indexes past its end. Texture tables likewise must match
the dummies created from material texture references. Keep each table dense,
including genuinely empty tables for transform-only models.
"""
import struct

def compact_material_table(data,definitions,renderer_slots):
    used=sorted({index for offset,index in renderer_slots})
    if any(index<0 or index>=len(definitions) for index in used):
        raise ValueError('Renderer references an undefined material')
    remap={old:new for new,old in enumerate(used)}
    for offset,old in renderer_slots:
        struct.pack_into('<i',data,offset,remap[old])
    materials=[definitions[index] for index in used]
    textures=list(dict.fromkeys(material[2] for material in materials))
    return materials,textures
