"""Read-only config audit, not ModuleManager/KSP execution. GPL-2.0-or-later."""
from pathlib import Path
import sys,json,copy,hashlib,argparse
ap=argparse.ArgumentParser();ap.add_argument('--patch-root',type=Path,default=Path(__file__).resolve().parent.parent);ap.add_argument('--upstream',type=Path,required=True);ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'Tests/native-docking-config-checks.json');args=ap.parse_args()
src=args.patch_root/'Source'
sys.path.insert(0,str(src))
sys.path.insert(0,str(src/'source_checks'))
from verify_package import parse,value
from source_checks.inspect_mu import nodes
import numpy as np
up=args.upstream
patches=parse((src.parent/'Patches/Mk33_FreeIVA.cfg').read_text())
report={'in_game_tested':False,'modulemanager_executed':False,'scope':'Exact original part configs plus limited structural application of own additive INTERNAL/ModuleFreeIva blocks; no execution of other installed mods.' ,'parts':{},'patch_sha256':hashlib.sha256((src.parent/'Patches/Mk33_FreeIVA.cfg').read_bytes()).hexdigest()}
for name,rel in [('Mk33ProbeCore','Control/Mk33ProbeCore.cfg'),('Mk33DockingNoseCone','Coupling/Mk33DockingNoseCone.cfg'),('wbiMk33KrewModule','Payload/crewModule.cfg')]:
 orig=parse((up/'Parts'/rel).read_text(encoding='utf-8-sig'))[0]
 patch=next(p for p in patches if p['type'].startswith('@PART['+name+']'))
 assert not patch['values']
 result=copy.deepcopy(orig)
 for c in patch['nodes']:
  assert c['type'] in ['%INTERNAL','%MODULE[ModuleFreeIva]']
  key='INTERNAL' if c['type']=='%INTERNAL' else 'MODULE'
  matches=[n for n in result['nodes'] if n['type']==key and (key=='INTERNAL' or value(n,'name')=='ModuleFreeIva')]
  if matches: dest=matches[0]
  else:
   dest={'type':key,'values':[],'nodes':[]};result['nodes'].append(dest)
  assert not c['nodes']
  for k,v in c['values']:
   assert k.startswith('%');k=k[1:]
   dest['values']=[(a,b) for a,b in dest['values'] if a!=k]+[(k,v)]
 assert result['values']==orig['values']
 assert result['nodes'][:len(orig['nodes'])]==orig['nodes']
 original_mods=[n for n in orig['nodes'] if n['type'].startswith('MODULE')]
 result_mods=[n for n in result['nodes'] if n['type'].startswith('MODULE')]
 assert result_mods[:len(original_mods)]==original_mods
 entry={'original_title':value(orig,'title'),'original_module_names':[value(n,'name') for n in original_mods],'original_modules_unchanged_and_same_order':True,'original_top_level_fields_unchanged':True,'added_module_names':[value(n,'name') for n in result_mods[len(original_mods):]],'source_cfg_sha256':hashlib.sha256((up/'Parts'/rel).read_bytes()).hexdigest()}
 dock=[n for n in original_mods if value(n,'name')=='ModuleDockingNode']
 entry['original_docking_module_count']=len(dock)
 if dock:
  d=dock[0];assert value(d,'nodeTransformName')=='dockingNode';assert value(d,'nodeType')=='size1';assert value(d,'deployAnimationController')=='1'
  assert value(result_mods[1],'name')=='ModuleAnimateGeneric'
  assert value(result_mods[1],'animationName')=='Deploy'
  entry['docking_fields']=dict(d['values'])
  ns=nodes(up/'Parts/SharedAssets'/('krewModule.mu' if name=='wbiMk33KrewModule' else 'dockingNoseCone.mu'));node=next(n for n in ns if n['name']=='dockingNode');mat=node['matrix']
  entry['docking_node_original_position_part_coordinates']=mat[:3,3][[0,2,1]].tolist()
  entry['deploy_animation_index_resolves_after_own_patch']=True
 report['parts'][name]=entry
report['sample_craft_variants']={}
for craft in ['SPH/Mk-33 LFO.craft','VAB/Mk-33.craft']:
 text=(up/'SampleCraft'/craft).read_text(encoding='utf-8-sig')
 roots=parse(text[text.index('\nPART\n')+1:])
 part_names=[value(n,'part').rsplit('_',1)[0] for n in roots]
 report['sample_craft_variants'][craft]={'has_probe_core':'Mk33ProbeCore' in part_names,'has_ordinary_nosecone':'Mk33NoseCone' in part_names,'has_shielded_docking_nosecone':'Mk33DockingNoseCone' in part_names}
assert report['sample_craft_variants']['SPH/Mk-33 LFO.craft']['has_ordinary_nosecone']
assert not report['sample_craft_variants']['SPH/Mk-33 LFO.craft']['has_shielded_docking_nosecone']
assert report['sample_craft_variants']['VAB/Mk-33.craft']['has_shielded_docking_nosecone']
report['conclusion']='No own-patch change to original docking-module settings, module order, deployment controller or external docking transform was found. Original ProbeCore is not a docking port; the separate shielded nosecone is. Runtime behavior of the separate docking nosecone has not been tested in KSP here.'
report['runtime_collision_or_craft_state_not_verified']=True
out=args.output
out.write_text(json.dumps(report,indent=2)+'\n')
print(out)
print(report['conclusion'])
