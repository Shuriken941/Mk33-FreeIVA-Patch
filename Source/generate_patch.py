"""Generate the reviewed ModuleManager configuration; GPL-2.0-or-later."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
PATCH=ROOT/'Patches'/'Mk33_FreeIVA.cfg'
PATCH.parent.mkdir(exist_ok=True)
NEEDS=':NEEDS[FreeIva,WildBlueIndustries/Mk-33]:BEFORE[FreeIva]'
def block(name,lines):
    return name+'\n{\n'+''.join('    '+line+'\n' for line in '\n'.join(lines).splitlines())+'}\n'
def module(name,*lines):return block('MODULE',['name = '+name,*lines])
def model(name):return block('MODEL',['model = '+name])
def vec(v):return ', '.join(str(x) for x in v)
def cut(target,pos,depth,radius=.525,rotation=(0,0,0)):
    return block('Cut',[f'target = {target}','type = ProceduralCylinder',f'radius = {radius}',f'height = {depth}','slices = 32','position = '+vec(pos),'rotation = '+vec(rotation),'scale = 1, 1, 1'])
def cube(target,pos,scale):return block('Cut',[f'target = {target}','type = Cube','position = '+vec(pos),'rotation = 0, 0, 0','scale = '+vec(scale)])
def hatch(pos,rot,attach='',airlock='',scale=1):
    return block('PROP',['name = Mk33FreeIVA_CircularHatch','position = '+vec(pos),'rotation = '+vec(rot),f'scale = {scale}, {scale}, {scale}',module('HatchConfig','attachNodeId = '+attach,'airlockName = '+airlock)])
def rail(name,center,size):return module('HandRail','transformName = '+name,block('Collider',['shape = Box','center = '+vec(center),'dimensions = '+vec(size)]))
def direct_door(pos,inwards,center,docking=False):
    extra=['dockingPortNodeName = dockingNode','requireDeploy = true','tubeTransformName = Mk33KrewDockTube'] if docking else []
    return module('Mk33FreeIvaHatch','attachNodeId =','doorTransformName = crewDoor','handleTransformName = Mk33DoorHandle','position = '+vec(pos),'inwardsDirection = '+vec(inwards),*extra,
        block('DoorCollider',['shape = Box','center = '+vec(center),'dimensions = 0.675879, 0.653811, 0.095096']),
        block('HandleCollider',['shape = Box','center = '+vec(pos),'dimensions = '+('0.42, 0.12, 0.42' if docking else '0.42, 0.42, 0.12')]))
def internal(name,sources,cuts,mask,extra_models=(),shells=(),features=()):
    needs=NEEDS if name!='wbiMk33ControlCabSpace' else NEEDS.replace('WildBlueIndustries/Mk-33]', 'WildBlueIndustries/Mk-33,SquadExpansion/Serenity]')
    return block(f'@INTERNAL[{name}]:HAS[!MODULE[InternalModuleFreeIva]]'+needs,[
        model('Mk33FreeIVA/Models/InteractionPoints'),*[model('Mk33FreeIVA/Models/'+m) for m in extra_models],
        module('Mk33FreeIvaGeometry',*['sourceTransform = '+s for s in sources],*cuts),
        module('InternalModuleFreeIva','shellColliderName = Mk33Shell',*['shellColliderName = '+s for s in shells],'externalDepthMaskFile = WildBlueIndustries/Mk-33/Parts/SharedAssets/'+mask),*features])
text='''// Mk33FreeIVA 0.1.0 -- KSP 1.12.5 / FreeIVA 0.2.20.2 validation candidate.
// Installed original IVA meshes are cut BEFORE identical nonconvex colliders
// are built. No original seats, models, external colliders, or part stats removed.
// BEFORE[FreeIva] also prevents guarded unfinished upstream main patches from
// deleting original seats. Other IVA replacements require separate validation.
// Do NOT add autoCutoutTargetName or later visual-only Cuts to these INTERNALs.

'''
for part in ['Mk33Cockpit','wbiMk33KrewModule','wbiMk33Airlock','wbiControlCab']:
    extras=['%deployAnimationName = Deploy'] if part=='wbiMk33KrewModule' else []
    text+=block('@PART['+part+']'+NEEDS,[block('%MODULE[ModuleFreeIva]',['%name = ModuleFreeIva','%allowsUnbuckling = true',*extras])])+'\n'
text+=block('@PART[Mk33MidTank]'+NEEDS,[block('%MODULE[ModuleFreeIva]',['%name = ModuleFreeIva','%passThroughNodeA = top','%passThroughNodeB = MissionModuleNode1','%allowsUnbuckling = false'])])+'\n'
text+=block('PROP:NEEDS[FreeIva]',['name = Mk33FreeIVA_CircularHatch',model('Mk33FreeIVA/Models/CircularHatch'),module('FreeIvaHatch','attachNodeId =','doorTransformName = door','handleTransformName = handleInside','handleTransformName = handleOutside','inwardsDirection = 0, 1, 0')])+'\n'
# Cockpit front original pressure cap remains closed. The aft corridor includes
# a sealed far-end hatch, preventing access to empty space if Krew is absent.
text+=internal('wbiMk33CockpitSpace',
    ['canopy','Dashboard','Screens','crewTube','windows']+[f'Seat{i:03}' for i in range(1,13)],
    [cut(t,(0,-.6503,-1.64),.14) for t in ['crewTube','Dashboard']],
    'cockpitDepthMask',['CockpitCorridor'],['Mk33CorridorShell'],[
        hatch((0,-.6503,-1.5674),(-.70710678,0,0,.70710678)),
        hatch((0,-.02293,2.78137),(-.70710678,0,0,.70710678),'bottom'),
        direct_door((0,1.496873,-.044039),(0,0,-1),(0,0,-.000001)),
        module('HandRail','transformName = Mk33AccessRail'),
        rail('Mk33RailOne',(1.836,-.16,-1.93),(.62,1.75,.64))])+'\n'
text+=internal('wbiMk33CrewModuleSpace',
    ['cabinMesh','crewTube','Screen','Screen001','Screen002','windows']+[f'Seat{i:03}' for i in range(1,17)],
    [cut(t,(0,-.025,z),.15) for t in ['crewTube','cabinMesh'] for z in [-1.23,1.08]]+
    [cube(t,(1.11893,1.80,.76054),(.62,.24,.70)) for t in ['crewTube','cabinMesh']],
    'crewModuleDepthMask',['KrewAirlockBridge','KrewDockTube'],['Mk33KrewAirlockBridgeShell'],[
        hatch((0,-.025,-1.1302),(.70710678,0,0,.70710678),'mount'),
        hatch((0,-.025,1.1502),(-.70710678,0,0,.70710678),'bottom'),
        direct_door((1.11893,1.82830,.76054),(0,-1,0),(0,0,.047532),True),
        rail('Mk33RailOne',(1.11893,.63,.76054),(.60,2.38,.68))])+'\n'
text+=internal('wbiMk33AirlockSpace',['airlockIVAMesh','Seat1','Seat2'],
    [cut('airlockIVAMesh',(0,0,-1.26),.18),cut('airlockIVAMesh',(0,0,1.02),.18),cut('airlockIVAMesh',(0,1.14,0),.18,rotation=(-90,0,0))],
    'airlockDepthMask',features=[
        hatch((0,0,-1.17922),(.70710678,0,0,.70710678),'top'),
        hatch((0,0,1.10120),(-.70710678,0,0,.70710678),'bottom','Airlock,0'),
        hatch((0,1.22697,0),(1,0,0,0),'airlockTop','Airlock,1'),
        rail('Mk33RailOne',(-.55,.20,-.55),(.42,1.60,.42)),
        rail('Mk33RailTwo',(0,.90,0),(.60,1.30,.60))])+'\n'
text+=internal('wbiMk33ControlCabSpace',['cabIVAMesh','ladder','Seat001','windows'],
    [cut('cabIVAMesh',(0,1.56,.17),.18,.50,(-90,0,0))],
    'controlCabDepthmask',features=[hatch((0,1.644332,.17),(1,0,0,0),airlock='Airlock'),rail('Mk33RailOne',(0,.60,.47),(.52,2.10,.42))])
PATCH.write_text(text,encoding='utf-8')
print(PATCH)
