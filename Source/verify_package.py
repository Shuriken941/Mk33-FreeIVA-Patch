"""Package/configuration checks. Python 3 stdlib. GPL-2.0-or-later.
Optional: python verify_package.py --gamedata /path/to/KSP/GameData
This is not a ModuleManager execution or Unity physics test.
"""
from pathlib import Path
import argparse, hashlib, json, re, struct
ROOT=Path(__file__).resolve().parent.parent
def parse(text):
    roots=[];stack=[roots];pending=None
    for number,line in enumerate(text.splitlines(),1):
        line=line.split('//',1)[0].strip().lstrip('\ufeff')
        if not line:continue
        if line=='{':
            assert pending is not None,('unexpected opening brace',number)
            node={'type':pending,'values':[],'nodes':[]};stack[-1].append(node);stack.append(node['nodes']);pending=None
        elif line=='}':
            assert pending is None and len(stack)>1,('unexpected closing brace',number)
            stack.pop()
        elif '=' in line:
            assert pending is None and len(stack)>1,('value outside node',number)
            key,value=line.split('=',1);parent=stack[-2][-1];parent['values'].append((key.strip(),value.strip()))
        else:
            assert pending is None,('missing brace',number,pending)
            pending=line
    assert len(stack)==1 and pending is None,'unclosed node'
    return roots
def value(n,key,default=None):return next((v for k,v in n['values'] if k==key),default)
def walk(ns):
    for n in ns:
        yield n
        yield from walk(n['nodes'])
def main():
    p=argparse.ArgumentParser();p.add_argument('--gamedata',type=Path);args=p.parse_args()
    roots=parse((ROOT/'Patches/Mk33_FreeIVA.cfg').read_text())
    interiors=[n for n in roots if n['type'].startswith('@INTERNAL[')]
    assert len(interiors)==4
    inventory=json.loads((ROOT/'Tests/source-mesh-inventory.json').read_text())
    original_models={'wbiMk33CockpitSpace':'cockpitIVA','wbiMk33CrewModuleSpace':'crewModuleIVA','wbiMk33AirlockSpace':'mk33AirlockSpace','wbiMk33ControlCabSpace':'controlCabIVA'}
    for n in interiors:
        mods=[value(c,'name') for c in n['nodes'] if c['type']=='MODULE']
        assert mods.count('Mk33FreeIvaGeometry')==1 and mods.count('InternalModuleFreeIva')==1
        assert mods.index('Mk33FreeIvaGeometry')<mods.index('InternalModuleFreeIva')
        geo=next(c for c in n['nodes'] if value(c,'name')=='Mk33FreeIvaGeometry')
        sources=[v for k,v in geo['values'] if k=='sourceTransform']
        assert len(sources)==len(set(sources)) and 'crewDoor' not in sources
        internal_name=n['type'].split('[',1)[1].split(']',1)[0]
        known={x['name']:x for x in inventory[original_models[internal_name]]}
        assert all(s in known and not known[s]['original_collider'] for s in sources),internal_name
        for c in geo['nodes']:
            assert c['type']=='Cut' and value(c,'target') in sources
        im=next(c for c in n['nodes'] if value(c,'name')=='InternalModuleFreeIva')
        assert not im['nodes'] and value(im,'autoCutoutTargetName') is None
        for prop in [c for c in n['nodes'] if c['type']=='PROP']:
            assert any(value(m,'name')=='HatchConfig' for m in prop['nodes'])
        assert not any('InternalSeat' in x['type'] for x in walk([n]))
    for part in [n for n in roots if n['type'].startswith('@PART[')]:
        assert not part['values']
        assert all(n['type']=='%MODULE[ModuleFreeIva]' for n in part['nodes'])
    models=[]
    for n in walk(roots):
        if n['type']=='MODEL':
            m=value(n,'model');assert m.startswith('Mk33FreeIVA/')
            f=ROOT.parent/(m+'.mu');assert f.is_file(),m
            assert struct.unpack('<2i',f.read_bytes()[:8])==(76543,5),m
            models.append(m)
        assert value(n,'cutoutTargetTransformName') is None
    dll=ROOT/'Plugins/Mk33FreeIVA.dll'
    assert dll.read_bytes()[:2]==b'MZ' and dll.stat().st_size>1000
    assert [x.name for x in (ROOT/'Plugins').glob('*.dll')]==['Mk33FreeIVA.dll']
    checks={'in_game_tested':False,'modulemanager_executed':False,'four_internal_patch_blocks':True,'post_cut_load_order':True,'no_fixed_door_copy':True,'no_later_visual_cut':True,'no_original_seat_removal':True,'part_stat_edits_absent':True,'local_model_references_resolve':True,'unique_models':sorted(set(models)),'only_own_runtime_dll':True}
    if args.gamedata:
        manifest=json.loads((ROOT/'Tests/source-manifest.json').read_text())
        mismatches=[]
        for path,expected in manifest['files'].items():
            f=args.gamedata/path
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=expected['sha256']:mismatches.append(path)
        checks['source_hash_mismatches']=mismatches
        assert not mismatches,('Different/missing upstream assets; revalidation needed',mismatches)
    (ROOT/'Tests/package-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
