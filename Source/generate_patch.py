"""Generate Mk33FreeIVA 0.3.5 configuration. GPL-2.0-or-later."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
PATCH=ROOT/'Patches'/'Mk33_FreeIVA.cfg'
PATCH.parent.mkdir(exist_ok=True)
DEFINITION_NEEDS=':NEEDS[Mk33FreeIVA,FreeIva,WildBlueIndustries/Mk-33]'
NEEDS=DEFINITION_NEEDS+':BEFORE[FreeIva]'

def block(name,lines):
    return name+'\n{\n'+''.join('    '+line+'\n' for line in '\n'.join(lines).splitlines())+'}\n'
def module(name,*lines):return block('MODULE',['name = '+name,*lines])
def model(name):return block('MODEL',['model = Mk33FreeIVA/Models/'+name])
def vec(v):return ', '.join(str(x) for x in v)
def cut(target,pos,depth,radius=.525,rotation=(0,0,0)):
    return block('Cut',[f'target = {target}','type = ProceduralCylinder',f'radius = {radius}',f'height = {depth}','slices = 32','position = '+vec(pos),'rotation = '+vec(rotation),'scale = 1, 1, 1'])
def cube(target,pos,scale):return block('Cut',[f'target = {target}','type = Cube','position = '+vec(pos),'rotation = 0, 0, 0','scale = '+vec(scale)])
def hatch(id,pos,rot,attach='',airlock='',local=False,docking=False,tube=''):
    fields=['hatchId = '+id,'position = '+vec(pos),'rotation = '+vec(rot),'attachNodeId = '+attach,'airlockName = '+airlock,'requireConnected = '+str(not local).lower()]
    if docking:fields+=['dockingPortNodeName = dockingNode','requireDeploy = true']
    if tube:fields+=['tubeTransformName = '+tube]
    return module('Mk33FreeIvaPressureHatch',*fields)
def rail(name,center,size):return module('HandRail','transformName = '+name,block('Collider',['shape = Box','center = '+vec(center),'dimensions = '+vec(size)]))
def direct_door(pos,inwards,center,docking=False,airlock=''):
    extra=['dockingPortNodeName = dockingNode','requireDeploy = true','tubeTransformName = Mk33KrewDockTube'] if docking else []
    return module('Mk33FreeIvaHatch','attachNodeId =','airlockName = '+airlock,'doorTransformName = crewDoor','handleTransformName = Mk33DoorHandle','centerHandlesOnHatch = true','position = '+vec(pos),'inwardsDirection = '+vec(inwards),*extra,
        block('DoorCollider',['shape = Box','center = '+vec(center),'dimensions = 0.675879, 0.653811, 0.095096']),
        block('HandleCollider',['shape = Box','center = 0, 0, 0','dimensions = '+('0.42, 0.12, 0.42' if abs(inwards[1])>.9 else '0.42, 0.42, 0.12')]))
def cockpit_lower_eva():
    # The lower-deck EXIT leaf is part of Dashboard. Native EVA immediately
    # leaves through the original exterior Airlock,0; it must NOT cut a hole
    # or hide the whole Dashboard. Detach only the three UNLOCK handle pieces
    # into the existing lifecycle-safe adapter; preserve the original wall.
    return module('Mk33FreeIvaHatch',
        'attachNodeId =', 'airlockName = Airlock,0',
        'doorTransformName = Mk33CockpitLowerEvaHandle',
        'extractSourceTransform = Dashboard',
        'extractBoundsMin = 2.60, -0.61, -2.365',
        'extractBoundsMax = 2.67, -0.49, -2.315',
        'extractExpectedTriangles = 104', 'centerHandlesOnHatch = true',
        'position = 2.630630, -0.549577, -2.340006',
        'inwardsDirection = -0.939693, 0, 0.342020',
        block('DoorCollider', ['shape = Box', 'center = 0, 0, 0',
                               'dimensions = 0.057, 0.111, 0.041']),
        block('HandleCollider', ['shape = Box', 'center = 0, 0, 0',
                                 'dimensions = 0.20, 0.32, 0.32']))

def central_airlock():
    return module('Mk33FreeIvaHatch',
        'attachNodeId =', 'airlockName =', 'doorTransformName = Mk33KrewCentralDoor',
        'extractSourceTransform = cabinMesh', 'extractBoundsMin = -0.34, 0.67, 0.02',
        'extractBoundsMax = 0.34, 1.44, 0.125', 'extractExpectedTriangles = 352',
        'centerHandlesOnHatch = true', 'position = 0, 1.055827, 0.096354',
        'inwardsDirection = 0, 0, 1', 'dockingPortNodeName = dockingNode',
        'requireDeploy = true', 'tubeTransformName = Mk33KrewDockTube',
        'autoOpenWhenDocked = true',
        block('DoorCollider', ['shape = Box', 'center = 0, 0, -0.025', 'dimensions = 0.675879, 0.759647, 0.1']),
        block('HandleCollider', ['shape = Box', 'center = 0, 0, 0', 'dimensions = 0.42, 0.42, 0.12']))

def internal(name,sources,cuts,mask,extra_models=(),shells=(),doors=(),hatch_ids=(),features=()):
    needs=NEEDS if name!='wbiMk33ControlCabSpace' else NEEDS.replace('WildBlueIndustries/Mk-33]', 'WildBlueIndustries/Mk-33,SquadExpansion/Serenity]')
    windows='windows' in sources
    # Pressure seals exist before visual cuts are permitted. The shell helper
    # verifies every required generated seal before it modifies original art.
    return block(f'@INTERNAL[{name}]:HAS[!MODULE[InternalModuleFreeIva]]'+needs,[
        model('InteractionPoints'),*[model(m) for m in extra_models],*doors,
        module('Mk33FreeIvaGeometry',*['requiredHatchId = '+s for s in hatch_ids],*['requiredShell = '+s for s in shells],*['requiredOriginalDoor = '+line.split('=',1)[1].strip() for d in doors for line in d.splitlines() if line.strip().startswith('doorTransformName =')],*['sourceTransform = '+s for s in sources],*cuts),
        *([module('Mk33FreeIvaWindowMask','sourceTransform = windows')] if windows else []),
        module('InternalModuleFreeIva','shellColliderName = Mk33Shell',*['shellColliderName = '+s for s in shells],'externalDepthMaskFile = WildBlueIndustries/Mk-33/Parts/SharedAssets/'+mask,*(['internalDepthMaskName = Mk33WindowDepthMask','windowName = windows'] if windows else [])),*features])

text='''// Mk33FreeIVA 0.3.5 -- KSP 1.12.5 / FreeIVA 0.2.20.2.
// Pressure doors are generated directly in INTERNAL before original cuts.
// The plugin assembly is required before enabling any of these walking IVAs.
// Native hatch connections and deployment checks remain in charge.
// No original seats/part statistics/exterior colliders are removed.

'''
for part in ['Mk33Cockpit','wbiMk33KrewModule','wbiMk33Airlock','wbiControlCab']:
    extra=['%deployAnimationName = Deploy'] if part=='wbiMk33KrewModule' else []
    text+=block('@PART['+part+']'+NEEDS,[block('%MODULE[ModuleFreeIva]',['%name = ModuleFreeIva','%allowsUnbuckling = true',*extra])])+'\n'
text+=block('@PART[Mk33MidTank]'+NEEDS,[block('%MODULE[ModuleFreeIva]',['%name = ModuleFreeIva','%passThroughNodeA = top','%passThroughNodeB = MissionModuleNode1','%allowsUnbuckling = false'])])+'\n'
text+=internal('wbiMk33CockpitSpace',
    ['canopy','Dashboard','Screens','crewTube','windows']+[f'Seat{i:03}' for i in range(1,13)],
    [cut(t,(0,-.6503,-1.64),.14) for t in ['crewTube','Dashboard']]+[cut(t,(0,-.6253,-2.84),.20) for t in ['crewTube','Dashboard']],
    'cockpitDepthMask',['CockpitCorridor'],['Mk33CorridorShell'],[
        hatch('CockpitAftEntry',(0,-.6503,-1.5674),(-.70710678,0,0,.70710678),local=True),
        hatch('CockpitAftExit',(0,-.02293,2.78137),(-.70710678,0,0,.70710678),'bottom'),
        hatch('CockpitNose',(0,-.6253,-2.72),(.70710678,0,0,.70710678),'top'),
        direct_door((0,1.496873,-.044039),(0,0,-1),(0,0,-.000001)),
        cockpit_lower_eva()],
    ['CockpitAftEntry','CockpitAftExit','CockpitNose'],[
        module('HandRail','transformName = Mk33AccessRail'),rail('Mk33RailOne',(1.836,-.16,-1.93),(.62,1.75,.64))])+'\n'
text+=internal('wbiMk33CrewModuleSpace',
    ['cabinMesh','crewTube','Screen','Screen001','Screen002','windows']+[f'Seat{i:03}' for i in range(1,17)],
    [cut(t,(0,-.025,z),.15) for t in ['crewTube','cabinMesh'] for z in [-1.23,1.08]]+
    [cube(t,(0,1.055827,.17),(.60,.70,.34)) for t in ['crewTube','cabinMesh']]+
    [cut(t,(0,1.76,.61551148),.18,.41,(-90,0,0)) for t in ['crewTube','cabinMesh']],
    'crewModuleDepthMask',['KrewAirlockBridge','KrewDockPassage','KrewDockTube'],['Mk33KrewAirlockBridgeShell','Mk33KrewDockPassageShell'],[
        hatch('KrewForward',(0,-.025,-1.1302),(.70710678,0,0,.70710678),'mount'),
        hatch('KrewAft',(0,-.025,1.1502),(-.70710678,0,0,.70710678),'bottom'),
        central_airlock(),
        direct_door((1.11893,1.82830,.76054),(0,-1,0),(0,0,.047532),airlock='Airlock,1')],
    ['KrewForward','KrewAft'],[
        rail('Mk33RailOne',(1.11893,.63,.76054),(.60,2.38,.68))])+'\n'
text+=internal('wbiMk33AirlockSpace',['airlockIVAMesh','Seat1','Seat2'],
    [cut('airlockIVAMesh',(0,0,-1.26),.18),cut('airlockIVAMesh',(0,0,1.02),.18),cut('airlockIVAMesh',(0,1.14,0),.18,rotation=(-90,0,0))],
    'airlockDepthMask',doors=[
        hatch('AirlockForward',(0,0,-1.17922),(.70710678,0,0,.70710678),'top'),
        hatch('AirlockRear',(0,0,1.10120),(-.70710678,0,0,.70710678),'bottom','Airlock,0'),
        hatch('AirlockRoof',(0,1.22697,0),(1,0,0,0),'airlockTop','Airlock,1')],
    hatch_ids=['AirlockForward','AirlockRear','AirlockRoof'],features=[
        rail('Mk33RailOne',(-.55,.20,-.55),(.42,1.60,.42)),rail('Mk33RailTwo',(0,.90,0),(.60,1.30,.60))])+'\n'
text+=internal('wbiMk33ControlCabSpace',['cabIVAMesh','ladder','Seat001','windows'],
    [cut('cabIVAMesh',(0,1.56,.17),.18,.50,(-90,0,0))],
    'controlCabDepthmask',doors=[hatch('ControlCabRoof',(0,1.644332,.17),(1,0,0,0),airlock='Airlock')],hatch_ids=['ControlCabRoof'],features=[rail('Mk33RailOne',(0,.60,.47),(.52,2.10,.42))])+'\n'
# The Probe Core is a separate zero-seat part. Its own INTERNAL carries both
# ends of the source-authored physical tunnel, including node1's real offset.
for part,space,deployment in [('Mk33ProbeCore','Mk33FreeIVA_ProbeCoreSpace',False),('Mk33DockingNoseCone','Mk33FreeIVA_NoseDockSpace',True)]:
    text+=block('@PART['+part+']'+NEEDS,[block('%INTERNAL',['%name = '+space]),block('%MODULE[ModuleFreeIva]',['%name = ModuleFreeIva','%allowsUnbuckling = false','%forceInternalCreation = true',*(['%deployAnimationName = Deploy'] if deployment else [])])])+'\n'
# Plain definitions accept NEEDS but cannot carry a ModuleManager pass. Their
# insertion precedes patch passes; BEFORE belongs only on modifying patches.
text+=block('INTERNAL'+DEFINITION_NEEDS,['name = Mk33FreeIVA_ProbeCoreSpace',model('ProbeCorePassage'),module('Mk33FreeIvaAuthoredShell','sourceTransform = Mk33ProbeCoreShell'),
    hatch('ProbeRear',(0,-.625,1.5852),(-.70710678,0,0,.70710678),'bottom'),
    hatch('ProbeFront',(-.0059150453,-.7693699002,-1.371947916),(.70710678,0,0,.70710678),'topNode'),
    module('InternalModuleFreeIva','shellColliderName = Mk33ProbeCoreShell','internalDepthMaskName =')])+'\n'
text+=block('INTERNAL'+DEFINITION_NEEDS,['name = Mk33FreeIVA_NoseDockSpace',model('NoseDockPassage'),module('Mk33FreeIvaAuthoredShell','sourceTransform = Mk33NoseDockShell'),
    hatch('NoseRear',(0,0,0),(-.70710678,0,0,.70710678),'bottom01'),
    hatch('NoseDock',(0,0,-.245),(.70710678,0,0,.70710678),docking=True,tube='Mk33NoseDockTube'),
    module('InternalModuleFreeIva','shellColliderName = Mk33NoseDockShell','internalDepthMaskName =')])+'\n'
PATCH.write_text(text,encoding='utf-8')
print(PATCH)
