"""Independent v034 -> v035 structural regression audit (not game execution).

Reads exact exported collider data and configuration, not generator reports.
The only permitted functional addition is a cockpit EVA hatch and its cuts.
Visual and window-mask changes are recorded separately.
"""
from pathlib import Path
import argparse, hashlib, json, sys, re

CURRENT=Path(__file__).resolve().parents[2]
BASE=None
sys.path.insert(0,str(CURRENT/'Source'))
sys.path.insert(0,str(CURRENT/'Source/source_checks'))
from verify_package import parse, value
from mu import Mu

def digest(data):
    if not isinstance(data,bytes): data=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()

def objects(obj, parent=()):
    path=parent+(obj.transform.name,)
    yield path,obj
    for child in obj.children:yield from objects(child,path)

def collider_snapshot(path):
    model=Mu().read(str(path)); result={}
    hierarchy={}
    for name,obj in objects(model.obj):
        t=obj.transform
        pose={'position':t.localPosition,'rotation':t.localRotation,'scale':t.localScale}
        hierarchy[name]=pose
        c=getattr(obj,'collider',None)
        if c is None:continue
        data={'type':type(c).__name__,'layer':obj.tag_and_layer.layer,
              'parent_poses':[hierarchy[name[:i]] for i in range(1,len(name)+1)]}
        for k,v in vars(c).items():
            if k=='mesh': data[k]={'verts':v.verts,'triangles':v.submeshes}
            else:data[k]=v
        result['/'.join(name)]={'sha256':digest(data),'type':type(c).__name__,'layer':data['layer'],
          'is_trigger':bool(getattr(c,'isTrigger',False)),
          'vertices':len(c.mesh.verts) if hasattr(c,'mesh') else None,
          'triangles':sum(map(len,c.mesh.submeshes)) if hasattr(c,'mesh') else None}
    return result

def selector(node):
    key=node['type'].split(':',1)[0]
    return key+'['+value(node,'name')+']' if key=='INTERNAL' else key

def nodes(root):return parse((root/'Patches/Mk33_FreeIVA.cfg').read_text())
def module(node,name):return [n for n in node['nodes'] if n['type']=='MODULE' and value(n,'name')==name]
def multiset_subset(a,b):
    remaining=list(b)
    for item in a:
        if item not in remaining:return False
        remaining.remove(item)
    return True

def extract_class(text,name):
    # Used only for preservation of entire unchanged core safety classes.
    pattern=r'\bclass\s+'+re.escape(name)+r'\b'
    m=re.search(pattern,text)
    if not m:return None
    start=text.find('{',m.end());level=0
    # Strip comments/strings while preserving character positions before braces.
    token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:[^"]|"")*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
    clean=token.sub(lambda m:' '*len(m.group()),text)
    for p in range(start,len(text)):
        if clean[p]=='{':level+=1
        elif clean[p]=='}':
            level-=1
            if level==0:return text[m.start():p+1]
    raise ValueError(name)

def main():
    global BASE
    ap=argparse.ArgumentParser();ap.add_argument('--current',type=Path,default=CURRENT)
    ap.add_argument('--baseline',type=Path,required=True,help='Extracted delivered v034 Mk33FreeIVA package root')
    ap.add_argument('--output',type=Path,default=CURRENT/'Tests/regression-preservation-checks.json')
    a=ap.parse_args();current=a.current;BASE=a.baseline
    report={'scope':'Independent exact exported collider and config comparison against delivered v034; no KSP/Unity/PhysX or ModuleManager execution.',
      'in_game_tested':False,'baseline':str(BASE),'current':str(current),'failures':[], 'checks':{}}
    failures=report['failures']
    def check(key,okay,details=None):
        report['checks'][key]={'pass':bool(okay),'details':details}
        if not okay:failures.append(key)
    oldcoll={p.name:collider_snapshot(p) for p in sorted((BASE/'Models').glob('*.mu'))}
    newcoll={p.name:collider_snapshot(p) for p in sorted((current/'Models').glob('*.mu'))}
    report['baseline_collider_manifest']=oldcoll
    for name,colliders in oldcoll.items():
        actual=newcoll.get(name,{})
        check('colliders_exact_'+name,colliders==actual,{'baseline_count':len(colliders),'current_count':len(actual),
          'changed_paths':[p for p in sorted(set(colliders)|set(actual)) if colliders.get(p)!=actual.get(p)]})
    check('new_models_no_physical_colliders',not any(v for k,v in newcoll.items() if k not in oldcoll),
          {k:v for k,v in newcoll.items() if k not in oldcoll})
    oldnodes=nodes(BASE);newnodes=nodes(current)
    newmap={selector(n):n for n in newnodes}
    for old in oldnodes:
        key=selector(old);new=newmap.get(key)
        check('existing_config_node_'+key,new is not None)
        if new is None:continue
        if key.startswith('@PART['):
            check('part_settings_exact_'+key,old==new)
            continue
        is_cockpit=key=='@INTERNAL[wbiMk33CockpitSpace]'
        for name in ['Mk33FreeIvaPressureHatch','Mk33FreeIvaHatch','HandRail','Mk33FreeIvaAuthoredShell']:
            before=module(old,name);after=module(new,name)
            # New cockpit EVA door may be appended; every old door remains intact.
            check(key+'_'+name+'_preserved',multiset_subset(before,after) if is_cockpit else before==after,
                  {'baseline_count':len(before),'current_count':len(after)})
        oldgeo=module(old,'Mk33FreeIvaGeometry');newgeo=module(new,'Mk33FreeIvaGeometry')
        if oldgeo:
            okay=len(newgeo)==1
            if okay:
                if is_cockpit:
                    okay=multiset_subset(oldgeo[0]['values'],newgeo[0]['values']) and multiset_subset(oldgeo[0]['nodes'],newgeo[0]['nodes'])
                else:okay=oldgeo==newgeo
            check(key+'_source_shell_and_cuts_preserved',okay)
        for oldim,newim in zip(module(old,'InternalModuleFreeIva'),module(new,'InternalModuleFreeIva')):
            oldshell=[v for k,v in oldim['values'] if k=='shellColliderName'];newshell=[v for k,v in newim['values'] if k=='shellColliderName']
            check(key+'_native_shell_bindings_preserved',oldshell==newshell,{'baseline':oldshell,'current':newshell})
        oldwindow=module(old,'Mk33FreeIvaWindowMask');newwindow=module(new,'Mk33FreeIvaWindowMask')
        report.setdefault('intentional_window_changes',{})[key]={'module_changed':oldwindow!=newwindow,
          'native_mask_fields_changed':module(old,'InternalModuleFreeIva')!=module(new,'InternalModuleFreeIva')}
    check('all_part_selectors_preserved',sorted(selector(n) for n in oldnodes if selector(n).startswith('@PART['))==sorted(selector(n) for n in newnodes if selector(n).startswith('@PART[')))
    oldpressure=(BASE/'Source/Mk33FreeIvaPressureHatch.cs').read_text();newpressure=(current/'Source/Mk33FreeIvaPressureHatch.cs').read_text()
    for cname in ['Mk33FreeIvaConnection','Mk33FreeIvaAuthoredShell','Mk33FreeIvaColliderSetup','Mk33FreeIvaWalkGate']:
        old=extract_class(oldpressure,cname);new=extract_class(newpressure,cname)
        check('core_class_exact_'+cname,old is not None and old==new,
              {'baseline_sha256':digest(old.encode()) if old else None,'current_sha256':digest(new.encode()) if new else None})
    report['file_changes']=[str(p.relative_to(current)) for p in current.rglob('*') if p.is_file() and '__pycache__' not in str(p)
      and (not (BASE/p.relative_to(current)).exists() or p.read_bytes()!=(BASE/p.relative_to(current)).read_bytes())]
    report['pass']=not failures
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'failed_checks':failures,'check_count':len(report['checks']),'output':str(a.output)},indent=2))
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
