// SPDX-License-Identifier: GPL-2.0-or-later
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using FreeIva;
using UnityEngine;

static class Program
{
    static readonly List<string> passed=new List<string>();
    sealed class Fixture
    {
        public Mk33FreeIvaPressureHatch hatch;public InternalModel model;public Part part;public Transform plate;public BoxCollider seal;public MeshRenderer renderer;
    }
    static void Assert(bool pass,string why){if(!pass)throw new Exception(why);}
    static void Scenario(string name,Action action){action();passed.Add(name);Console.WriteLine("PASS "+name);}
    static Part NewPart(Vessel vessel=null)
    {
        var go=new GameObject("part");var p=go.AddComponent<Part>();p.vessel=vessel??new Vessel();return p;
    }
    static T Module<T>(Part p) where T:PartModule,new(){var m=p.gameObject.AddComponent<T>();m.part=p;p.Modules.Add(m);return m;}
    static MeshCollider ImportedShell(InternalModel model,string name,bool convex=true)
    {
        var go=new GameObject(name);go.layer=16;go.transform.SetParent(model.transform,false);
        var c=go.AddComponent<MeshCollider>();c.convex=convex;c.sharedMesh=new Mesh{vertices=new[]{Vector3.zero,new Vector3(1,0,0),new Vector3(0,1,0)},triangles=new[]{0,1,2}};return c;
    }
    static Fixture Hatch(bool local=false,bool completeShell=true,string id="test",InternalModel existingModel=null,Part existingPart=null,bool scopedWrapper=false,bool noNativeReparent=false,bool failNativeAwake=false)
    {
        var model=existingModel??new GameObject("internal").AddComponent<InternalModel>();InternalModuleFreeIva.Register(model);
        if(completeShell && model.transform.Find("Mk33Shell")==null){var shell=new GameObject("Mk33Shell");shell.transform.SetParent(model.transform,false);shell.AddComponent<Mk33ColliderMarker>().complete=true;}
        var go=new GameObject("module_"+id);go.transform.SetParent(model.transform,false);
        var h=go.AddComponent<Mk33FreeIvaPressureHatch>();h.internalModel=model;h.part=existingPart??NewPart();h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;h.internalProp.hasModel=scopedWrapper;h.DoNotReparentNativeDoor=noNativeReparent;h.FailNativeAwakeAfterOpen=failNativeAwake;if(failNativeAwake)Module<ModuleFreeIva>(h.part);
        var cfg=new ConfigNode();cfg.AddValue("hatchId",id);cfg.AddValue("requireConnected",!local);cfg.AddValue("attachNodeId",local?"":"bottom");cfg.AddValue("position","1, 2, 3");cfg.AddValue("rotation","0.7071068, 0, 0, 0.7071068");h.OnLoad(cfg);h.OnAwake();StartModule(h);
        var plate=model.GetComponentsInChildren<Transform>(true).Single(t=>t.name=="Mk33Pressure_"+id+"_Door");
        return new Fixture{hatch=h,model=model,part=h.part,plate=plate,seal=plate.GetComponent<BoxCollider>(),renderer=plate.GetComponent<MeshRenderer>()};
    }
    static FreeIvaHatch Peer(Part p,string id="top")
    {
        var h=new GameObject("nativePeer").AddComponent<FreeIvaHatch>();h.part=p;h.attachNodeId=id;return h;
    }
    static void Connect(Part a,string nodeA,Part b,string nodeB){a.attachNodes.Add(new AttachNode{id=nodeA,attachedPart=b});b.attachNodes.Add(new AttachNode{id=nodeB,attachedPart=a});}
    static FreeIvaHatch StackPeer(Fixture f)
    {
        var p=NewPart(f.part.vessel);Connect(f.part,"bottom",p,"top");var peer=Peer(p);f.hatch.ConnectedHatch=peer;peer.ConnectedHatch=f.hatch;return peer;
    }
    static void StartModule(object h){var method=h.GetType().GetMethod("Start",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public);if(method!=null)method.Invoke(h,null);}
    static void Tick(object h){h.GetType().GetMethod("LateUpdate",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(h,null);}
    static void Closed(Fixture f){Assert(!f.hatch.IsOpen && f.plate.gameObject.activeSelf && f.seal.enabled && !f.seal.isTrigger && f.seal.gameObject.layer==16,"door not physically closed");Assert(f.renderer.enabled && f.renderer.sharedMaterial.color.a==1,"closed plate not opaque and enabled");}
    static void Opened(Fixture f){Assert(f.hatch.IsOpen && !f.plate.gameObject.activeSelf && !f.seal.enabled,"open plate/collider still obstruct route");Assert(f.hatch.HandleTransforms.All(t=>t.gameObject.activeInHierarchy),"persistent closing handles disappeared");}
    sealed class OriginalFixture { public Mk33FreeIvaHatch hatch; public Transform door,art; public BoxCollider seal; public Part part; public Mk33OriginalHatchMarker marker; public ConfigNode config; }
    static OriginalFixture Original(bool docking=true,bool completeShell=true,bool scopedWrapper=false,bool noNativeReparent=false,string renderLayout="mesh",bool legacyMarker=true,bool artPresent=true,bool failNativeAwake=false)
    {
        var model=new GameObject("originalInternal").AddComponent<InternalModel>();InternalModuleFreeIva.Register(model);
        if(completeShell){var shell=new GameObject("Mk33Shell");shell.transform.SetParent(model.transform,false);shell.AddComponent<Mk33ColliderMarker>().complete=true;}
        GameObject plate=null;
        if(artPresent)
        {
            plate=new GameObject("crewDoor");plate.layer=16;plate.transform.SetParent(model.transform,false);plate.transform.localPosition=new Vector3(1.11893f,1.82830f,.76054f);plate.transform.localRotation=new Quaternion(-.7071068f,0,0,.7071068f);
            var material=new Material(Shader.Find("KSP/Diffuse"));material.color=new Color(1,1,1,1);
            if(renderLayout=="mesh")plate.AddComponent<MeshRenderer>().sharedMaterial=material;
            else if(renderLayout=="skinned")plate.AddComponent<SkinnedMeshRenderer>().sharedMaterial=material;
            else if(renderLayout=="nested")for(int i=0;i<2;i++){var visual=new GameObject("nestedDoorVisual"+i);visual.transform.SetParent(plate.transform,false);visual.AddComponent<MeshRenderer>().sharedMaterial=material;}
            var seal=plate.AddComponent<BoxCollider>();seal.size=new Vector3(.67f,.65f,.095f);
        }
        if(legacyMarker){var handle=new GameObject("Mk33DoorHandle");handle.layer=20;handle.transform.SetParent(model.transform,false);handle.AddComponent<BoxCollider>();}
        if(docking)ImportedShell(model,"Mk33KrewDockTube");
        var go=new GameObject("originalAdapter");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaHatch>();h.part=NewPart();h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;h.internalProp.hasModel=scopedWrapper;h.DoNotReparentNativeDoor=noNativeReparent;h.FailNativeAwakeAfterOpen=failNativeAwake;if(failNativeAwake)Module<ModuleFreeIva>(h.part);
        var cfg=new ConfigNode();cfg.AddValue("attachNodeId","");cfg.AddValue("airlockName","");cfg.AddValue("dockingPortNodeName",docking?"dockingNode":"");cfg.AddValue("tubeTransformName",docking?"Mk33KrewDockTube":"");cfg.AddValue("requireDeploy",docking);cfg.AddValue("doorTransformName","crewDoor");cfg.AddValue("inwardsDirection",docking?"0,-1,0":"0,0,-1");cfg.AddValue("handleTransformName","Mk33DoorHandle");cfg.AddValue("centerHandlesOnHatch",true);cfg.AddValue("position","1.11893,1.82830,.76054");
        var doorCollider=cfg.AddNode("DoorCollider");doorCollider.AddValue("shape","Box");doorCollider.AddValue("center","0,0,.047532");doorCollider.AddValue("dimensions",".675879,.653811,.095096");
        var handleCollider=cfg.AddNode("HandleCollider");handleCollider.AddValue("shape","Box");handleCollider.AddValue("center","0,0,0");handleCollider.AddValue("dimensions",".42,.12,.42");
        h.OnLoad(cfg);h.OnAwake();StartModule(h);
        var marked=h.transform.GetComponentsInChildren<Transform>(true).FirstOrDefault(t=>t.GetComponent<Mk33OriginalHatchMarker>()!=null);
        Assert(marked!=null,"original adapter created no door/fallback marker");var marker=marked.GetComponent<Mk33OriginalHatchMarker>();var actual=marker.sealedDoor??marked;
        return new OriginalFixture{hatch=h,door=actual,art=marked,marker=marker,seal=actual.GetComponentsInChildren<BoxCollider>(true).FirstOrDefault(),part=h.part,config=cfg};
    }
    static ModuleDockingNode DockPeer(FreeIvaHatch h)
    {
        var p=NewPart(h.part.vessel);var peer=Peer(p);h.ConnectedHatch=peer;peer.ConnectedHatch=h;var dock=Module<ModuleDockingNode>(h.part);dock.nodeTransformName="dockingNode";dock.state="Docked (docker)";dock.otherNode=Module<ModuleDockingNode>(p);return dock;
    }
    static Mk33FreeIvaAuthoredShell Authored(InternalModel model,string name,bool solid=true)
    {
        var go=new GameObject("authoredValidator");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaAuthoredShell>();h.internalModel=model;h.part=NewPart();Module<ModuleFreeIva>(h.part);
        if(name!="missing"){var source=new GameObject(name);source.layer=solid?16:20;source.transform.SetParent(model.transform,false);var c=source.AddComponent<MeshCollider>();c.sharedMesh=new Mesh{vertices=new[]{new Vector3(0,0,0),new Vector3(1,0,0),new Vector3(0,1,0)},triangles=new[]{0,1,2}};}
        var cfg=new ConfigNode();cfg.AddValue("sourceTransform",name);h.OnLoad(cfg);h.OnAwake();StartModule(h);return h;
    }
    sealed class LifecycleFixture<T> where T:InternalModule
    {
        public T module; public Part part; public InternalModel model; public ConfigNode valid;
        public ModuleFreeIva walking {get{return part.GetComponent<ModuleFreeIva>();}}
    }
    static LifecycleFixture<T> Lifecycle<T>(string id,bool nativeReady=true,bool configuredWalking=true,Part existingPart=null,InternalModel existingModel=null) where T:InternalModule,new()
    {
        var model=existingModel??new GameObject("lifecycle_"+id).AddComponent<InternalModel>();var part=existingPart??NewPart();var walking=part.GetComponent<ModuleFreeIva>();if(walking==null)walking=Module<ModuleFreeIva>(part);if(existingPart==null)walking.allowsUnbuckling=configuredWalking;
        if(nativeReady)InternalModuleFreeIva.Register(model);else InternalModuleFreeIva.Unregister(model);
        if(typeof(T)!=typeof(Mk33FreeIvaAuthoredShell) && typeof(T)!=typeof(Mk33FreeIvaGeometry) && model.transform.Find("Mk33Shell")==null){var shell=new GameObject("Mk33Shell");shell.transform.SetParent(model.transform,false);shell.AddComponent<Mk33ColliderMarker>().complete=true;}
        var go=new GameObject("lifecycleModule_"+id);go.transform.SetParent(model.transform,false);var h=go.AddComponent<T>();h.part=part;h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;h.internalProp.hasModel=true;
        var cfg=new ConfigNode();
        if(typeof(T)==typeof(Mk33FreeIvaPressureHatch)){cfg.AddValue("hatchId",id);cfg.AddValue("requireConnected",false);cfg.AddValue("position","1,2,3");}
        else if(typeof(T)==typeof(Mk33FreeIvaHatch))
        {
            var art=new GameObject("crewDoor");art.layer=16;art.transform.SetParent(model.transform,false);art.AddComponent<MeshRenderer>().sharedMaterial=new Material(Shader.Find("KSP/Diffuse"));cfg.AddValue("doorTransformName","crewDoor");cfg.AddValue("position","1,2,3");
            var seal=cfg.AddNode("DoorCollider");seal.AddValue("shape","Box");seal.AddValue("center","0,0,0");seal.AddValue("dimensions",".67,.65,.095");
        }
        else if(typeof(T)==typeof(Mk33FreeIvaGeometry))
        {
            var source=new GameObject("lifecycleSource_"+id);source.transform.SetParent(model.transform,false);source.AddComponent<MeshFilter>().sharedMesh=new Mesh{vertices=new[]{Vector3.zero,new Vector3(1,0,0),new Vector3(0,1,0)},triangles=new[]{0,1,2}};cfg.AddValue("sourceTransform",source.name);
        }
        else if(typeof(T)==typeof(Mk33FreeIvaAuthoredShell))
        {
            var shell=new GameObject("lifecycleAuthoredShell_"+id);shell.layer=16;shell.transform.SetParent(model.transform,false);shell.AddComponent<MeshCollider>().sharedMesh=new Mesh{vertices=new[]{Vector3.zero,new Vector3(1,0,0),new Vector3(0,1,0)},triangles=new[]{0,1,2}};cfg.AddValue("sourceTransform",shell.name);
        }
        return new LifecycleFixture<T>{module=h,model=model,part=part,valid=cfg};
    }
    static void ReadyOriginal<T>(LifecycleFixture<T> f) where T:InternalModule
    {
        f.module.OnLoad(f.valid);f.module.OnAwake();StartModule(f.module);
    }
    static void ImportedShellScenarios()
    {
        // The actual KSPCF 1.41.1 parser forces imported MeshCollider2.convex=true.
        // Mirror that single assignment here; this harness does not run the parser.
        Scenario("parser-forced convex corridor is normalized before geometry readiness",()=>{
            var f=Lifecycle<Mk33FreeIvaGeometry>("forcedCorridor");
            var corridor=ImportedShell(f.model,"Mk33CorridorShell");
            var unrelated=ImportedShell(f.model,"UnreferencedConvexDoor");
            var door=new GameObject("originalBoxDoor");door.transform.SetParent(f.model.transform,false);var box=door.AddComponent<BoxCollider>();box.size=new Vector3(.67f,.65f,.095f);
            f.valid.AddValue("requiredShell","Mk33CorridorShell");ReadyOriginal(f);
            Assert(!corridor.convex,"declared imported corridor stayed convex");
            Assert(f.model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>().complete&&f.walking.allowsUnbuckling,"normalized corridor failed geometry readiness");
            Assert(unrelated.convex&&box.enabled&&!box.isTrigger&&box.size.z==.095f,"normalization changed an unrelated convex collider or original box seal");
        });
        Scenario("parser-forced convex probe and nose authored shells validate in place",()=>{
            foreach(var name in new[]{"Mk33ProbeCoreShell","Mk33NoseDockShell"})
            {
                var f=Lifecycle<Mk33FreeIvaAuthoredShell>("forced_"+name);
                var c=f.model.GetComponentsInChildren<MeshCollider>(true).Single();c.convex=true;
                ReadyOriginal(f);
                Assert(!c.convex&&f.model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>().complete,"authored imported shell remained convex or incomplete");
                Assert(f.walking.allowsUnbuckling&&f.model.GetComponentsInChildren<MeshCollider>(true).Length==1,"authored normalization duplicated colliders or blocked walking");
            }
        });
        Scenario("original Krew named dynamic tube is nonconvex before native hatch load",()=>{
            var f=Original();var c=f.hatch.internalModel.GetComponentsInChildren<Transform>(true).Single(t=>t.name=="Mk33KrewDockTube").GetComponent<MeshCollider>();
            Assert(!c.convex&&f.hatch.NamedTubeConvexAtBaseLoad==false&&f.hatch.baseLoadCalls==1,"original tube normalization happened after native load or not at all");
            Assert(f.seal.enabled&&!f.seal.isTrigger&&f.seal.size.z>.09f,"tube setup changed original pressure box");
        });
        Scenario("pressure Nose named dynamic tube is nonconvex before native hatch load",()=>{
            var f=Lifecycle<Mk33FreeIvaPressureHatch>("forcedNoseTube");var c=ImportedShell(f.model,"Mk33NoseDockTube");
            f.valid.AddValue("tubeTransformName","Mk33NoseDockTube");ReadyOriginal(f);
            Assert(!c.convex&&f.module.NamedTubeConvexAtBaseLoad==false&&f.module.baseLoadCalls==1,"pressure tube normalization happened after native load or not at all");
            Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==1,"valid dynamic tube prevented initialization");
        });
        foreach(var defect in new[]{"layer","trigger","disabled","empty","missing mesh"})
        {
            string test=defect;
            Scenario("imported-shell normalization still rejects "+test,()=>{
                var model=new GameObject("invalidImported").AddComponent<InternalModel>();var c=ImportedShell(model,"BadShell");
                if(test=="layer")c.gameObject.layer=20;
                else if(test=="trigger")c.isTrigger=true;
                else if(test=="disabled")c.enabled=false;
                else if(test=="empty")c.sharedMesh=new Mesh{vertices=new Vector3[0],triangles=new int[0]};
                else c.sharedMesh=null;
                bool rejected=false;try{Mk33FreeIvaColliderSetup.PrepareImportedShell(c.transform,"test shell");}catch(InvalidOperationException){rejected=true;}
                Assert(rejected&&c.convex,"invalid shell was accepted or mutated");
                Assert(test!="layer"||c.gameObject.layer==20,"invalid layer silently repaired");
                Assert(test!="trigger"||c.isTrigger,"trigger silently repaired");
                Assert(test!="disabled"||!c.enabled,"disabled collider silently repaired");
            });
        }
        Scenario("imported-shell validation checks all colliders before any convex mutation",()=>{
            var model=new GameObject("compoundImported").AddComponent<InternalModel>();var root=new GameObject("DeclaredShell");root.transform.SetParent(model.transform,false);
            var first=ImportedShell(model,"FirstValid");first.transform.SetParent(root.transform,false);var second=ImportedShell(model,"SecondInvalid");second.transform.SetParent(root.transform,false);second.isTrigger=true;
            bool rejected=false;try{Mk33FreeIvaColliderSetup.PrepareImportedShell(root.transform,"compound shell");}catch(InvalidOperationException){rejected=true;}
            Assert(rejected&&first.convex&&second.convex&&second.isTrigger,"compound failure partly mutated its source");
        });
        Scenario("missing declared corridor still blocks geometry and walking",()=>{
            var f=Lifecycle<Mk33FreeIvaGeometry>("missingCorridor");f.valid.AddValue("requiredShell","AbsentCorridor");ReadyOriginal(f);
            Assert(f.model.transform.Find("Mk33Shell")==null&&!f.walking.allowsUnbuckling,"missing auxiliary shell was bypassed");
        });
        Scenario("invalid declared corridor layer and trigger still block actual geometry readiness",()=>{
            foreach(var defect in new[]{"layer","trigger"})
            {
                var f=Lifecycle<Mk33FreeIvaGeometry>("invalidCorridor_"+defect);var c=ImportedShell(f.model,"Mk33CorridorShell");
                if(defect=="layer")c.gameObject.layer=20;else c.isTrigger=true;
                f.valid.AddValue("requiredShell","Mk33CorridorShell");ReadyOriginal(f);
                Assert(c.convex&&f.model.transform.Find("Mk33Shell")==null&&!f.walking.allowsUnbuckling,"invalid declared corridor was normalized or authorized walking");
            }
        });
        Scenario("missing named dynamic tube keeps pressure sealed and skips native load",()=>{
            var f=Lifecycle<Mk33FreeIvaPressureHatch>("missingDynamicTube");f.valid.AddValue("tubeTransformName","AbsentTube");ReadyOriginal(f);
            var plate=f.model.GetComponentsInChildren<Transform>(true).Single(t=>t.name=="Mk33Pressure_missingDynamicTube_Door");
            Assert(f.module.baseLoadCalls==0&&f.module.baseAwakeCalls==0&&!f.walking.allowsUnbuckling,"missing named tube reached native load or enabled walking");
            Assert(plate.gameObject.activeSelf&&plate.GetComponent<BoxCollider>().enabled,"missing tube left its pressure plate unsealed");
        });
    }
    sealed class ExtractFixture
    {
        public Mk33FreeIvaHatch hatch;public InternalModel model;public MeshFilter source;public Mesh original;public Transform roof;public Material material;public ConfigNode config;
    }
    static ExtractFixture Extracted(string variant = "valid")
    {
        var model = new GameObject("extractionInternal").AddComponent<InternalModel>();
        model.transform.localPosition = new Vector3(4, -2, 7);
        model.transform.localRotation = new Quaternion(0, .38268343f, 0, .92387953f);
        InternalModuleFreeIva.Register(model);
        var shell = new GameObject("Mk33Shell");shell.transform.SetParent(model.transform, false);shell.AddComponent<Mk33ColliderMarker>().complete = true;
        var roof = new GameObject("crewDoor");roof.transform.SetParent(model.transform, false);roof.transform.localPosition = new Vector3(1.11893f, 1.8283f, .76054f);roof.AddComponent<MeshRenderer>().sharedMaterial = new Material(Shader.Find("KSP/Diffuse"));
        var source = new GameObject("cabinMesh");source.transform.SetParent(model.transform, false);
        source.transform.localPosition = new Vector3(.12f, -.18f, .22f);source.transform.localScale = new Vector3(1.2f, .8f, 1.1f);source.transform.localRotation = new Quaternion(.25881904f, 0, 0, .96592583f);
        var sourceFromInternal = source.transform.worldToLocalMatrix * model.transform.localToWorldMatrix;
        var internalPoints = new[]{new Vector3(-.2f,.8f,.08f),new Vector3(.2f,.8f,.08f),new Vector3(.2f,1.3f,.08f),new Vector3(-.2f,1.3f,.08f),new Vector3(1,1,0),new Vector3(1.2f,1,0),new Vector3(1,1.2f,0)};
        var vertices = internalPoints.Select(v => sourceFromInternal.MultiplyPoint3x4(v)).ToArray();
        var mesh = new Mesh{vertices=vertices,normals=Enumerable.Repeat(new Vector3(0,0,-1),7).ToArray(),tangents=Enumerable.Repeat(new Vector4(1,0,0,1),7).ToArray(),uv=Enumerable.Range(0,7).Select(i=>new Vector2(i/7f,1-i/7f)).ToArray(),subMeshCount=2};
        mesh.SetTriangles(new[]{0,1,2,0,2,3},0);mesh.SetTriangles(new[]{4,5,6},1);
        var filter=source.AddComponent<MeshFilter>();filter.sharedMesh=mesh;
        var material=new Material(Shader.Find("KSP/Diffuse"));source.AddComponent<MeshRenderer>().sharedMaterials=new[]{material,material};
        ImportedShell(model,"Mk33KrewDockTube");
        var go=new GameObject("centralAdapter");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaHatch>();h.part=NewPart();Module<ModuleFreeIva>(h.part);h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;
        var cfg=new ConfigNode();cfg.AddValue("doorTransformName","Mk33KrewCentralDoor");cfg.AddValue("extractSourceTransform",variant=="missing"?"missing":"cabinMesh");cfg.AddValue("extractBoundsMin","-.34,.67,.02");cfg.AddValue("extractBoundsMax",variant=="bounds"?".34,.60,.125":".34,1.44,.125");cfg.AddValue("extractExpectedTriangles",variant=="count"?3:2);cfg.AddValue("position","0,1.055827,.096354");cfg.AddValue("inwardsDirection","0,0,-1");cfg.AddValue("centerHandlesOnHatch",true);cfg.AddValue("autoOpenWhenDocked",true);cfg.AddValue("dockingPortNodeName","dockingNode");cfg.AddValue("requireDeploy",true);cfg.AddValue("tubeTransformName","Mk33KrewDockTube");
        var collider=cfg.AddNode("DoorCollider");collider.AddValue("shape","Box");collider.AddValue("center","0,0,-.025");collider.AddValue("dimensions",".675879,.759647,.1");
        if(variant=="solidSource")source.AddComponent<BoxCollider>();
        if(variant=="nonfinite"){var changed=mesh.vertices;changed[0]=new Vector3(Single.NaN,0,0);mesh.vertices=changed;}
        h.OnLoad(cfg);h.OnAwake();StartModule(h);
        return new ExtractFixture{hatch=h,model=model,source=filter,original=mesh,roof=roof.transform,material=material,config=cfg};
    }
    static void CentralDoorScenarios()
    {
        Scenario("central AIRLOCK extraction detaches only selected triangles with original texture channels and pose",()=>{
            var f=Extracted();var door=f.model.GetComponentsInChildren<Transform>(true).Single(t=>t.name=="Mk33KrewCentralDoor");var mesh=door.GetComponent<MeshFilter>().sharedMesh;
            Assert(f.hatch.baseAwakeCalls==1&&door.GetComponent<Mk33ExtractedDoorMarker>().complete,"extracted door failed native registration");
            Assert(f.source.sharedMesh!=f.original&&f.source.sharedMesh.triangles.SequenceEqual(new[]{4,5,6})&&f.original.triangles.Length==9,"source/installed art was mutated or wrong triangles remain");
            Assert(mesh.triangles.SequenceEqual(new[]{0,1,2,0,2,3})&&mesh.subMeshCount==2,"detached triangles/submesh mapping changed");
            Assert(door.GetComponent<MeshRenderer>().sharedMaterials.All(m=>m==f.material)&&mesh.uv.Length==f.original.uv.Length,"original material or UV channels missing");
            foreach(int i in mesh.triangles.Distinct()){
                Assert((door.TransformPoint(mesh.vertices[i])-f.source.transform.TransformPoint(f.original.vertices[i])).magnitude<.00002f,"textured door geometry moved under transformed source/model hierarchy");
                Assert(mesh.uv[i].x==f.original.uv[i].x&&mesh.uv[i].y==f.original.uv[i].y,"source UV changed");
                Assert(Math.Abs(mesh.normals[i].magnitude-1)<.00001f&&Math.Abs(new Vector3(mesh.tangents[i].x,mesh.tangents[i].y,mesh.tangents[i].z).magnitude-1)<.00001f,"normal/tangent transform invalid");
            }
            Assert((f.roof.localPosition-new Vector3(1.11893f,1.8283f,.76054f)).magnitude<.00001f&&f.roof.parent==f.model.transform,"neighboring exterior roof hatch was repurposed");
            Assert(mesh.bounds.size.x<.41f&&mesh.bounds.size.y<.51f&&mesh.bounds.size.z<.001f,"unreferenced source vertices inflated detached-door bounds");
            int count=f.model.GetComponentsInChildren<Mk33ExtractedDoorMarker>(true).Length;f.hatch.OnLoad(f.config);Assert(f.model.GetComponentsInChildren<Mk33ExtractedDoorMarker>(true).Length==count,"repeated load detached door twice");
        });
        foreach(string variant in new[]{"count","bounds","missing","solidSource","nonfinite"})Scenario("central AIRLOCK extraction rejects "+variant+" without changing source art or enabling walking",()=>{
            var f=Extracted(variant);Assert(f.source.sharedMesh==f.original&&f.original.triangles.Length==9,"failed extraction changed installed/source geometry");
            Assert(!f.model.GetComponentsInChildren<Mk33ExtractedDoorMarker>(true).Any(m=>m.complete)&&f.hatch.baseAwakeCalls==0,"failed extraction authorized native hatch or cut");Assert(!f.hatch.part.GetComponent<ModuleFreeIva>().allowsUnbuckling,"failed extraction did not protect walking");
        });
        Scenario("central AIRLOCK automatically disappears only for a deployed physical dock and reseals on undock",()=>{
            var f=Extracted();var marker=f.model.GetComponentsInChildren<Mk33OriginalHatchMarker>(true).Single();var door=marker.sealedDoor;
            Tick(f.hatch);Assert(!f.hatch.IsOpen&&door.gameObject.activeSelf,"undocked door automatically opened");
            var dock=DockPeer(f.hatch);Assert(f.hatch.requireDeploy,"central door lost its requireDeploy configuration");f.hatch.blockedByAnimation=true;Tick(f.hatch);Assert(!f.hatch.IsOpen&&door.gameObject.activeSelf,"retracted docking tube opened central door");
            f.hatch.blockedByAnimation=false;Tick(f.hatch);Assert(f.hatch.IsOpen&&!door.gameObject.activeSelf&&!door.GetComponentsInChildren<Collider>(true).Any(c=>c.enabled&&c.gameObject.layer==16),"deployed physical dock did not clear the textured door and seal");
            dock.state="Ready";dock.otherNode=null;Tick(f.hatch);Assert(!f.hatch.IsOpen&&door.gameObject.activeSelf&&door.GetComponentsInChildren<Collider>(true).Any(c=>c.enabled&&c.gameObject.layer==16),"undock failed to restore solid pressure door");
        });
        Scenario("central AIRLOCK auto-open rejects cached incompatible peer and peer deployment lock",()=>{
            var f=Extracted();var dock=DockPeer(f.hatch);f.hatch.ConnectedHatch.blockedByAnimation=true;Tick(f.hatch);Assert(!f.hatch.IsOpen,"locked peer deployment did not block auto-open");
            f.hatch.ConnectedHatch.blockedByAnimation=false;dock.otherNode=Module<ModuleDockingNode>(NewPart(f.hatch.part.vessel));Tick(f.hatch);Assert(!f.hatch.IsOpen,"cached unrelated peer enabled central auto-open");
        });
        Scenario("central AIRLOCK auto-open stays sealed while peer or own physical shell is incomplete",()=>{
            var f=Extracted();var dock=DockPeer(f.hatch);var peer=Original(true,false);peer.part.vessel=f.hatch.part.vessel;f.hatch.ConnectedHatch=peer.hatch;peer.hatch.ConnectedHatch=f.hatch;dock.otherNode=Module<ModuleDockingNode>(peer.part);dock.otherNode.nodeTransformName="dockingNode";dock.otherNode.state="Docked (dockee)";dock.otherNode.otherNode=dock;
            Tick(f.hatch);Assert(!f.hatch.IsOpen,"incomplete peer shell allowed automatic pressure-door opening");
            var shell=new GameObject("Mk33Shell");shell.transform.SetParent(peer.hatch.internalModel.transform,false);var marker=shell.AddComponent<Mk33ColliderMarker>();marker.complete=true;Tick(f.hatch);Assert(f.hatch.IsOpen,"completed peer shell did not permit physical dock opening");
            marker.complete=false;Tick(f.hatch);Assert(!f.hatch.IsOpen,"loss of peer shell did not reseal automatically");marker.complete=true;f.model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>().complete=false;Tick(f.hatch);Assert(!f.hatch.IsOpen,"own incomplete shell allowed central auto-open");
        });
        Scenario("ordinary cockpit and exterior hatch adapters retain manual opening behavior",()=>{
            var local=Original(false);Tick(local.hatch);Assert(!local.hatch.autoOpenWhenDocked&&!local.hatch.IsOpen,"ordinary original door auto-opened");local.hatch.SetOpened(true);Tick(local.hatch);Assert(local.hatch.IsOpen,"manual cockpit door no longer stays open");
            var dock=Original(true);DockPeer(dock.hatch);Tick(dock.hatch);Assert(!dock.hatch.IsOpen,"default original hatch acquired automatic behavior");
        });
    }
    sealed class ClassicSource
    {
        public GameObject root,leaf;public Mesh mesh;public Material material;
    }
    static ClassicSource InstallClassicSource()
    {
        var root=new GameObject("FreeIVAClassicPrefab");root.transform.localPosition=new Vector3(5,6,7);root.transform.localRotation=new Quaternion(.7071068f,0,0,.7071068f);
        var leaf=new GameObject("Hatch_Size1_Door");leaf.transform.SetParent(root.transform,false);leaf.transform.localPosition=new Vector3(-.1f,.02f,0);
        var material=new Material(Shader.Find("KSP/Bumped Specular")){color=new Color(.8f,.9f,1,1),mainTexture=new Texture(),renderQueue=2000};
        var vertices=new Vector3[120];var normals=new Vector3[120];var uvs=new Vector2[120];var tangents=new Vector4[120];
        for(int i=0;i<120;i++){double angle=i*Math.PI*2/120;vertices[i]=new Vector3(.1f+.41f*(float)Math.Cos(angle),0,.41f*(float)Math.Sin(angle));normals[i]=Vector3.up;uvs[i]=new Vector2(i/120f,0);tangents[i]=new Vector4(1,0,0,1);}
        var mesh=new Mesh{name="sourceClassicLeaf",vertices=vertices,normals=normals,uv=uvs,tangents=tangents,triangles=new[]{0,1,2}};leaf.AddComponent<MeshFilter>().sharedMesh=mesh;leaf.AddComponent<MeshRenderer>().sharedMaterial=material;leaf.AddComponent<BoxCollider>();
        for(int side=-1;side<=1;side+=2){var handle=new GameObject("handle_"+side);handle.transform.SetParent(leaf.transform,false);handle.transform.localPosition=new Vector3(.1f,side*.07f,0);handle.AddComponent<MeshFilter>().sharedMesh=new Mesh{vertices=new[]{Vector3.zero,new Vector3(.03f,0,0),new Vector3(0,0,.03f)},triangles=new[]{0,1,2},uv=new[]{new Vector2(0,0),new Vector2(1,0),new Vector2(0,1)}};handle.AddComponent<MeshRenderer>().sharedMaterial=material;handle.AddComponent<BoxCollider>();}
        var tube=new GameObject("tube");tube.transform.SetParent(root.transform,false);tube.AddComponent<BoxCollider>();
        GameDatabase.Instance.modelPrefabs["FreeIva/Props/FreeIva_Hatch_Round_Size1"]=root;
        return new ClassicSource{root=root,leaf=leaf,mesh=mesh,material=material};
    }
    static void WithClassic(Action<ClassicSource> action)
    {
        var source=InstallClassicSource();try{action(source);}finally{GameDatabase.Instance.modelPrefabs.Clear();}
    }
    static void ClassicHatchScenarios()
    {
        Scenario("classic FreeIVA leaf and both handles copy as render-only decoration",()=>WithClassic(source=>{var f=Hatch(true);Closed(f);var visual=f.plate.Find("Mk33Pressure_test_ClassicVisual");Assert(visual!=null&&visual.gameObject.activeSelf,"classic visual was not selected");Assert(visual.GetComponentsInChildren<MeshRenderer>(true).Length==3,"leaf or both classic handles absent");Assert(visual.GetComponentsInChildren<Collider>(true).Length==0,"dependency colliders leaked into authored geometry");Assert(f.plate.GetComponentsInChildren<Collider>(true).Length==1,"pressure seal was replaced or duplicated");Assert(f.plate.GetComponentsInChildren<MeshRenderer>(true).Length==4,"temporary handle decoration remains behind classic leaf");Assert(f.plate.GetComponent<Mk33PressurePlateMarker>().complete,"cosmetic replacement prevented readiness");}));
        Scenario("classic copy preserves source assets material and UVs without mutation",()=>WithClassic(source=>{var before=source.mesh.vertices;var f=Hatch(true);var visual=f.plate.Find("Mk33Pressure_test_ClassicVisual");var copy=visual.GetComponentsInChildren<MeshFilter>(true).Single(x=>x.name.EndsWith("Hatch_Size1_Door"));Assert(copy.sharedMesh!=source.mesh,"source mesh was modified directly");Assert(source.mesh.vertices.Zip(before,(a,b)=>(a-b).magnitude).All(x=>x==0),"dependency mesh changed");Assert(copy.sharedMesh.uv.Length==source.mesh.uv.Length&&copy.sharedMesh.tangents.Length==source.mesh.tangents.Length,"UVs/tangents lost");Assert(visual.GetComponentsInChildren<MeshRenderer>(true).All(r=>r.sharedMaterial==source.material),"classic material was replaced");Assert(source.material.color.a==1&&source.material.color.r==.8f&&source.material.mainTexture!=null&&source.material.renderQueue==2000,"source material was modified");Assert(Math.Abs(copy.sharedMesh.vertices[0].x-.545f)<.0001f&&Math.Abs(copy.sharedMesh.vertices[0].y-.02f*.545f/.41f)<.0001f,"closed pose root or hinge transform baked incorrectly");}));
        Scenario("classic porthole insert stays opaque while full original pressure seal remains",()=>WithClassic(source=>{var f=Hatch(true);var mesh=f.plate.GetComponent<MeshFilter>().sharedMesh;Assert(Math.Abs(mesh.vertices.Max(v=>Math.Sqrt(v.x*v.x+v.z*v.z))-.145)<.00001,"porthole backing not fitted");Assert(Math.Abs(f.seal.size.x-1.09f)<.00001&&Math.Abs(f.seal.size.z-1.09f)<.00001&&Math.Abs(f.seal.size.y-.06f)<.00001,"cosmetic insert shrank physical seal");Assert(f.renderer.sharedMaterial.color.a==1&&f.renderer.sharedMaterial.mainTexture==null,"porthole insert not opaque");foreach(var renderer in f.plate.GetComponentsInChildren<MeshRenderer>(true))renderer.enabled=false;Tick(f.hatch);Assert(f.plate.GetComponentsInChildren<MeshRenderer>(true).All(r=>r.enabled),"closed classic visual not restored after IVA culling");Closed(f);}));
        Scenario("opening classic hatch removes leaf both handles and insert but preserves click targets",()=>WithClassic(source=>{var f=Hatch(true);f.hatch.SetOpened(true);Opened(f);Assert(f.plate.GetComponentsInChildren<MeshRenderer>(true).All(r=>!r.gameObject.activeInHierarchy),"classic decoration floats in open passage");f.hatch.SetOpened(false);Closed(f);Assert(f.plate.GetComponentsInChildren<MeshRenderer>(true).All(r=>r.gameObject.activeInHierarchy&&r.enabled),"classic decoration did not return on closure");}));
        Scenario("classic cosmetic selection preserves physical docking gate and undock closure",()=>WithClassic(source=>{var f=Hatch();f.hatch.attachNodeId="";f.hatch.dockingPortNodeName="dockingNode";f.hatch.SetOpened(true);Closed(f);var dock=DockPeer(f.hatch);f.hatch.SetOpened(true);Opened(f);dock.otherNode=null;Tick(f.hatch);Closed(f);}));
        Scenario("missing classic named leaf retains full opaque fallback and active walking",()=>WithClassic(source=>{source.leaf.name="unknownLeaf";var f=Hatch(true);Closed(f);Assert(f.plate.Find("Mk33Pressure_test_ClassicVisual")==null,"invalid named leaf accepted");Assert(f.plate.GetComponentsInChildren<MeshRenderer>(true).Length==7,"fallback handles missing");Assert(Math.Abs(f.plate.GetComponent<MeshFilter>().sharedMesh.vertices[0].x-.545f)<.00001,"fallback was shrunk despite missing classic model");f.hatch.SetOpened(true);Opened(f);}));
        Scenario("incomplete classic handle material falls back without partial visible decoration",()=>WithClassic(source=>{source.leaf.transform.GetChild(1).GetComponent<MeshRenderer>().sharedMaterial=null;var f=Hatch(true);Closed(f);var visual=f.plate.Find("Mk33Pressure_test_ClassicVisual");Assert(visual!=null&&!visual.gameObject.activeSelf,"partial copied classic decoration visible");Assert(Math.Abs(f.plate.GetComponent<MeshFilter>().sharedMesh.vertices[0].x-.545f)<.00001,"incomplete classic decoration shrank opaque fallback");Tick(f.hatch);Assert(!visual.gameObject.activeInHierarchy,"state repair enabled incomplete classic decoration");f.hatch.SetOpened(true);Opened(f);}));
        Scenario("nonfinite classic mesh fails cosmetic selection without blocking movement",()=>WithClassic(source=>{var v=source.mesh.vertices;v[0].x=Single.NaN;source.mesh.vertices=v;var f=Hatch(true);Closed(f);var visual=f.plate.Find("Mk33Pressure_test_ClassicVisual");Assert(visual!=null&&!visual.gameObject.activeSelf,"invalid source geometry is visible");Assert(f.plate.GetComponent<Mk33PressurePlateMarker>().complete,"optional art failure blocked known-good pressure seal");f.hatch.SetOpened(true);Opened(f);}));
    }
    static void Main(string[] args)
    {
        Scenario("closed initialization creates opaque plate and primitive layer16 seal",()=>{var f=Hatch();Closed(f);Assert(f.plate.GetComponent<Mk33PressurePlateMarker>().complete,"pressure marker not complete");Assert(f.hatch.GetComponent<HatchConfig>()!=null,"missing explicit config sentinel");Assert(f.hatch.baseAwakeCalls==1,"native Awake not reached");});
        Scenario("generated plate triangles face outward and cap the opening",()=>{var f=Hatch();var m=f.plate.GetComponent<MeshFilter>().sharedMesh;Assert(m.vertices.Length==66 && m.triangles.Length==384,"unexpected plate mesh");for(int i=0;i<m.triangles.Length;i+=3){var a=m.vertices[m.triangles[i]];var b=m.vertices[m.triangles[i+1]];var c=m.vertices[m.triangles[i+2]];double ux=b.x-a.x,uy=b.y-a.y,uz=b.z-a.z,vx=c.x-a.x,vy=c.y-a.y,vz=c.z-a.z;double dot=(uy*vz-uz*vy)*(a.x+b.x+c.x)+(uz*vx-ux*vz)*(a.y+b.y+c.y)+(ux*vy-uy*vx)*(a.z+b.z+c.z);Assert(dot>0,"inward or degenerate plate triangle");}Assert(f.seal.size.x>=1.05 && f.seal.size.z>=1.05 && f.seal.size.y>0,"primitive plate does not cover 1.05m circular aperture");});
        Scenario("visible hardware belongs to door and click targets survive opening",()=>{var f=Hatch(true);Assert(f.plate.GetComponentsInChildren<MeshRenderer>(true).Length==7,"physical handle bars/feet absent");Assert(f.hatch.HandleTransforms.Length==2 && f.hatch.HandleTransforms.All(t=>!t.IsChildOf(f.plate)&&t.gameObject.layer==20),"closing handle lifetime/layer wrong");f.hatch.SetOpened(true);Opened(f);f.hatch.SetOpened(false);Closed(f);});
        Scenario("unbound connector rejects local and remote native open requests",()=>{var f=Hatch();f.hatch.SetOpened(true);Closed(f);var peer=Peer(NewPart(f.part.vessel));peer.ConnectedHatch=f.hatch;f.hatch.ConnectedHatch=peer;peer.SetOpened(true);Closed(f);Assert(!peer.IsOpen,"rejected remote opening left peer open");});
        Scenario("valid reciprocal stack opens and closes normally",()=>{var f=Hatch();var peer=StackPeer(f);f.hatch.SetOpened(true);Opened(f);Assert(peer.IsOpen,"native reciprocal opening absent");f.hatch.SetOpened(false);Closed(f);Assert(!peer.IsOpen,"native reciprocal closing absent");});
        Scenario("passthrough chain follows paired logical nodes",()=>{var f=Hatch();var tank=NewPart(f.part.vessel);var p=NewPart(f.part.vessel);var pass=Module<ModuleFreeIva>(tank);pass.passThroughNodeA="top";pass.passThroughNodeB="mission";Connect(f.part,"bottom",tank,"top");Connect(tank,"mission",p,"top");var peer=Peer(p);f.hatch.ConnectedHatch=peer;peer.ConnectedHatch=f.hatch;f.hatch.SetOpened(true);Opened(f);tank.FindAttachNode("mission").attachedPart=null;Tick(f.hatch);Closed(f);});
        Scenario("stale native cached peer cannot keep an undocked stack open",()=>{var f=Hatch();StackPeer(f);f.hatch.SetOpened(true);Opened(f);f.part.FindAttachNode("bottom").attachedPart=null;Tick(f.hatch);Closed(f);Assert(f.hatch.ConnectedHatch!=null,"test should preserve stale native peer");});
        Scenario("peer on a different vessel forces closure",()=>{var f=Hatch();var peer=StackPeer(f);f.hatch.SetOpened(true);Opened(f);peer.part.vessel=new Vessel();Tick(f.hatch);Closed(f);});
        Scenario("dock requires real Docked state and correct otherNode part",()=>{var f=Hatch();f.hatch.attachNodeId="";f.hatch.dockingPortNodeName="dockingNode";var p=NewPart(f.part.vessel);var peer=Peer(p);f.hatch.ConnectedHatch=peer;peer.ConnectedHatch=f.hatch;var own=Module<ModuleDockingNode>(f.part);own.nodeTransformName="dockingNode";own.state="Docked (dockee)";own.otherNode=Module<ModuleDockingNode>(p);f.hatch.SetOpened(true);Opened(f);own.state="Ready";Tick(f.hatch);Closed(f);own.state="Docked (dockee)";own.otherNode=null;f.hatch.SetOpened(true);Closed(f);});
        Scenario("deployment folding closes an already opened passage",()=>{var f=Hatch();StackPeer(f);f.hatch.SetOpened(true);Opened(f);f.hatch.blockedByAnimation=true;Tick(f.hatch);Closed(f);f.hatch.SetOpened(true);Closed(f);});
        Scenario("EVA remains native action with pressure plate sealed",()=>{var f=Hatch();f.hatch.CanEVA=true;f.hatch.airlockName="Airlock";f.hatch.SetOpened(true);Closed(f);Assert(f.hatch.evaCalls==1,"native EVA action not reached");});
        Scenario("missing own shell rejects opening including local interior hatch",()=>{var f=Hatch(true,false);f.hatch.SetOpened(true);Closed(f);});
        Scenario("incomplete Mk33 peer shell rejects opening",()=>{var f=Hatch();var other=Hatch(false,false,"peer",null,NewPart(f.part.vessel));Connect(f.part,"bottom",other.part,"bottom");f.hatch.ConnectedHatch=other.hatch;other.hatch.ConnectedHatch=f.hatch;f.hatch.SetOpened(true);Closed(f);});
        Scenario("closed state repairs inactive object renderer and collider flags",()=>{var f=Hatch();f.plate.gameObject.SetActive(false);f.renderer.enabled=false;f.seal.enabled=false;f.seal.isTrigger=true;f.seal.gameObject.layer=20;Tick(f.hatch);Closed(f);});
        Scenario("distinct IDs bind distinct doors in same INTERNAL",()=>{var f=Hatch(true,true,"first");var other=Hatch(true,true,"second",f.model,f.part);f.hatch.SetOpened(true);Opened(f);Closed(other);Assert(f.hatch.HandleTransforms.All(t=>t.name.Contains("first")),"handle lookup crossed modules");});
        Scenario("missing texture keeps an opaque generated fallback plate",()=>{GameDatabase.Instance.missingTexture=true;try{var f=Hatch();Closed(f);Assert(f.renderer.sharedMaterial.mainTexture==null,"texture fallback scenario not reached");}finally{GameDatabase.Instance.missingTexture=false;}});
        Scenario("repeat Awake does not reset deliberate open state",()=>{var f=Hatch(true);f.hatch.SetOpened(true);Opened(f);f.hatch.OnAwake();Opened(f);});
        Scenario("authored solid shell marks readiness without copying colliders",()=>{var model=new GameObject("authoredInternal").AddComponent<InternalModel>();var h=Authored(model,"Mk33NoseDockShell");var marker=model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>();Assert(marker.complete&&marker.sourceCount==1,"valid authored shell rejected");Assert(model.GetComponentsInChildren<MeshCollider>(true).Length==1,"validator duplicated physical collision");var f=Hatch(true,false,"authoredDoor",model,h.part);f.hatch.SetOpened(true);Opened(f);});
        Scenario("invalid authored shell remains incomplete and doors stay sealed",()=>{var model=new GameObject("invalidAuthored").AddComponent<InternalModel>();var h=Authored(model,"badLayer",false);var marker=model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>();Assert(!marker.complete,"invalid authored shell marked complete");Assert(!h.part.GetComponent<ModuleFreeIva>().allowsUnbuckling,"failed authored shell still allows unbuckling");var f=Hatch(true,false,"unsafeDoor",model,h.part);f.hatch.SetOpened(true);Closed(f);});
        Scenario("missing authored shell source does not authorize a hatch",()=>{var model=new GameObject("missingAuthored").AddComponent<InternalModel>();Authored(model,"missing");Assert(!model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>().complete,"missing authored source marked complete");});
        Scenario("original door initializes closed with centered persistent handle",()=>{var f=Original();Assert(!f.hatch.IsOpen&&f.door.gameObject.activeSelf&&f.seal.enabled,"original door not closed");Assert(f.marker.complete,"original door seal validation incomplete");Assert(f.hatch.HandleTransforms.Single().parent==f.hatch.transform,"original handle not attached to hatch origin");Assert(f.hatch.HandleTransforms.Single().localPosition.x==0&&f.hatch.HandleTransforms.Single().localPosition.y==0,"original handle offset persisted");Assert(f.hatch.tubeTransformName=="Mk33KrewDockTube"&&f.hatch.requireDeploy,"explicit original dock config missing");});
        Scenario("original docking door opens only with valid peer and closes on undock",()=>{var f=Original();f.hatch.SetOpened(true);Assert(!f.hatch.IsOpen&&f.seal.enabled,"unbound original dock opened");var dock=DockPeer(f.hatch);f.hatch.SetOpened(true);Assert(f.hatch.IsOpen&&!f.door.gameObject.activeSelf&&!f.seal.enabled,"valid original dock blocked");dock.otherNode=null;Tick(f.hatch);Assert(!f.hatch.IsOpen&&f.door.gameObject.activeSelf&&f.seal.enabled,"lost original dock did not seal");});
        Scenario("original docking retraction seals its active door",()=>{var f=Original();DockPeer(f.hatch);f.hatch.SetOpened(true);Assert(f.hatch.IsOpen,"original dock setup did not open");f.hatch.blockedByAnimation=true;Tick(f.hatch);Assert(!f.hatch.IsOpen&&f.seal.enabled,"folded original docking hatch remains open");});
        Scenario("original local corridor door still opens with a complete shell",()=>{var f=Original(false);f.hatch.SetOpened(true);Assert(f.hatch.IsOpen&&!f.seal.enabled,"local original corridor door blocked");f.hatch.SetOpened(false);Assert(!f.hatch.IsOpen&&f.seal.enabled,"original local corridor failed to close");});
        Scenario("original door with incomplete shell stays closed",()=>{var f=Original(false,false);f.hatch.SetOpened(true);Assert(!f.hatch.IsOpen&&f.seal.enabled,"unsafe original door opened");});
        Scenario("scoped wrapper resolves original art outside prop before native lookup",()=>{var f=Original(true,true,true,true);Assert(f.door.IsChildOf(f.hatch.transform),"door remained outside scoped wrapper");Assert(f.hatch.HandleTransforms.Length>0,"native scoped loader received no handle");Assert(f.door.gameObject.activeSelf&&f.seal.enabled,"scoped original plate not sealed");Assert((f.art.position-new Vector3(1.11893f,1.82830f,.76054f)).magnitude<.0001,"hatch position was applied twice");});
        Scenario("adapter moves door itself when native does not reparent",()=>{var f=Original(true,true,false,true);Assert(f.door.IsChildOf(f.hatch.transform),"adapter depended on native reparent");var dock=DockPeer(f.hatch);f.hatch.SetOpened(true);Assert(f.hatch.IsOpen&&!f.seal.enabled,"self-contained original door did not open");dock.otherNode=null;Tick(f.hatch);Assert(!f.hatch.IsOpen&&f.seal.enabled,"self-contained original door did not close");});
        Scenario("missing legacy interaction marker is recreated under adapter",()=>{var f=Original(false,true,true,true,"mesh",false);Assert(f.hatch.HandleTransforms.Length>0,"legacy marker absent left no interaction target");Assert(f.hatch.HandleTransforms.All(t=>t.IsChildOf(f.hatch.transform)&&!t.IsChildOf(f.door)),"new handle lifetime/scope invalid");f.hatch.SetOpened(true);Assert(f.hatch.IsOpen,"marker fallback local hatch blocked");});
        Scenario("skinned original door renderer is accepted and restored",()=>{var f=Original(false,true,true,true,"skinned",false);Assert(f.door.GetComponentsInChildren<SkinnedMeshRenderer>(true).Length==1,"skinned art replaced unnecessarily");var r=f.art.GetComponent<SkinnedMeshRenderer>();r.enabled=false;Tick(f.hatch);Assert(r.enabled&&f.seal.enabled,"skinned closed door not restored");});
        Scenario("multi-mesh nested original art is accepted without root renderer",()=>{var f=Original(false,true,true,true,"nested",false);Assert(f.door.GetComponentsInChildren<Renderer>(true).Length==2,"nested artwork not preserved");f.hatch.SetOpened(true);Assert(f.hatch.IsOpen&&!f.door.gameObject.activeSelf,"nested art did not follow door");f.hatch.SetOpened(false);Assert(f.seal.enabled&&f.door.gameObject.activeSelf,"nested art did not close");});
        Scenario("missing original artwork creates visible sealed fallback rather than loader exception",()=>{var f=Original(false,true,true,true,"mesh",false,false);Assert(f.door.GetComponentsInChildren<Renderer>(true).Length>0,"fallback plate is invisible");Assert(f.seal!=null&&f.seal.enabled&&!f.seal.isTrigger&&f.seal.gameObject.layer==16,"fallback plate is not solid");Assert(f.marker.complete,"fallback readiness marker incomplete");});
        Scenario("invalid pressure hatch ID logs load failure without throwing",()=>{var model=new GameObject("invalidPressure").AddComponent<InternalModel>();var go=new GameObject("invalidPressureModule");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaPressureHatch>();h.part=NewPart();h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;var cfg=new ConfigNode();int before=Debug.logs.Count;h.OnLoad(cfg);h.OnAwake();Assert(Debug.logs.Count>before,"invalid pressure ID not diagnosed");Assert(!model.GetComponentsInChildren<Mk33PressurePlateMarker>(true).Any(m=>m.complete),"invalid pressure ID authorized a cut");});
        Scenario("invalid pressure radius logs load failure without throwing",()=>{var model=new GameObject("invalidRadius").AddComponent<InternalModel>();var go=new GameObject("invalidRadiusModule");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaPressureHatch>();h.part=NewPart();h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;var cfg=new ConfigNode();cfg.AddValue("hatchId","invalidRadius");cfg.AddValue("doorRadius",.1f);int before=Debug.logs.Count;h.OnLoad(cfg);h.OnAwake();Assert(Debug.logs.Count>before,"invalid pressure radius not diagnosed");Assert(!model.GetComponentsInChildren<Mk33PressurePlateMarker>(true).Any(m=>m.complete),"invalid pressure radius authorized a cut");});
        Scenario("missing pressure loader context logs safely without marker",()=>{var h=new GameObject("noPressureContext").AddComponent<Mk33FreeIvaPressureHatch>();var cfg=new ConfigNode();cfg.AddValue("hatchId","noContext");int before=Debug.logs.Count;h.OnLoad(cfg);h.OnAwake();Assert(Debug.logs.Count>before,"missing pressure context not diagnosed");});
        Scenario("missing opaque shader logs pressure load failure without throwing",()=>{var model=new GameObject("noShader").AddComponent<InternalModel>();var go=new GameObject("noShaderModule");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaPressureHatch>();h.part=NewPart();h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;var cfg=new ConfigNode();cfg.AddValue("hatchId","shaderFailure");cfg.AddValue("position","2,3,4");cfg.AddValue("rotation","0,0,1,0");Shader.Missing.UnionWith(new[]{"KSP/Diffuse","KSP/Unlit","Unlit/Color"});try{int before=Debug.logs.Count;h.OnLoad(cfg);h.OnAwake();Assert(Debug.logs.Count>before,"shader failure not diagnosed");Assert((h.transform.localPosition-new Vector3(2,3,4)).magnitude<.0001&&h.transform.localRotation.z==1&&h.transform.localRotation.w==0,"pressure pose was not applied before native/material loading failed");var partialPlate=h.transform.Find("Mk33Pressure_shaderFailure_Door");Assert(partialPlate!=null&&(partialPlate.position-new Vector3(2,3,4)).magnitude<.0001,"partial pressure plate was created at the wrong pose");Assert(!model.GetComponentsInChildren<Mk33PressurePlateMarker>(true).Any(m=>m.complete),"shader failure authorized a cut");}finally{Shader.Missing.Clear();}});
        Scenario("missing authored-shell loader context logs rather than escaping",()=>{var h=new GameObject("noAuthoredContext").AddComponent<Mk33FreeIvaAuthoredShell>();int before=Debug.logs.Count;h.OnLoad(new ConfigNode());h.OnAwake();Assert(Debug.logs.Count>before,"missing authored context not diagnosed");});
        Scenario("duplicate authored-shell marker is diagnosed without loader exception",()=>{var model=new GameObject("duplicateMarker").AddComponent<InternalModel>();var marker=new GameObject("Mk33Shell");marker.transform.SetParent(model.transform,false);marker.AddComponent<Mk33ColliderMarker>().complete=true;var go=new GameObject("duplicateValidator");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaAuthoredShell>();h.internalModel=model;h.part=NewPart();int before=Debug.logs.Count;h.OnLoad(new ConfigNode());Assert(Debug.logs.Count>before,"duplicate authored readiness marker not diagnosed");});
        Scenario("generated pressure plate works in scoped wrapper without native reparent",()=>{var f=Hatch(true,true,"scopedPressure",null,null,true,true);Closed(f);Assert(f.plate.IsChildOf(f.hatch.transform)&&f.hatch.HandleTransforms.Length==2,"generated geometry not scoped to its module");f.hatch.SetOpened(true);Opened(f);f.hatch.SetOpened(false);Closed(f);});
        Scenario("fallback docking plate uses configured inward plane and toggles with native state",()=>{var f=Original(true,true,true,true,"mesh",false,false);var plate=f.door.GetComponentsInChildren<MeshRenderer>(true).Single().transform;var normal=plate.localRotation*Vector3.forward;Assert(Vector3.Dot(normal,new Vector3(0,-1,0))>.999,"fallback seal was built in wrong door plane");DockPeer(f.hatch);f.hatch.SetOpened(true);Assert(f.hatch.IsOpen&&!f.door.gameObject.activeSelf&&!f.seal.enabled,"fallback dock plate did not clear route");f.hatch.SetOpened(false);Assert(f.door.gameObject.activeSelf&&f.seal.enabled,"fallback dock plate did not reseal");});
        Scenario("repeated original load does not duplicate proxies or interaction handles",()=>{var f=Original(false,true,true,true,"nested",false);int transformCount=f.hatch.GetComponentsInChildren<Transform>(true).Length;var target=f.hatch.HandleTransforms.Single();f.hatch.OnLoad(f.config);Assert(f.hatch.GetComponentsInChildren<Transform>(true).Length==transformCount,"repeated native load duplicated pressure geometry");Assert(f.hatch.HandleTransforms.Single()==target,"repeated load replaced persistent interaction target");});
        Scenario("missing original loader context is contained without native Awake",()=>{var h=new GameObject("noOriginalContext").AddComponent<Mk33FreeIvaHatch>();int before=Debug.logs.Count;h.OnLoad(new ConfigNode());h.OnAwake();Assert(Debug.logs.Count>before&&h.baseAwakeCalls==0,"missing context reached native Awake or was not diagnosed");});
        Scenario("missing fallback shader cannot mark original hatch complete or crash loading",()=>{Shader.Missing.UnionWith(new[]{"KSP/Diffuse","KSP/Unlit","Unlit/Color","Standard"});try{var model=new GameObject("noOriginalShader").AddComponent<InternalModel>();var go=new GameObject("noOriginalShaderModule");go.transform.SetParent(model.transform,false);var h=go.AddComponent<Mk33FreeIvaHatch>();h.part=NewPart();h.internalModel=model;h.internalProp=go.AddComponent<InternalProp>();h.internalProp.internalModel=model;h.internalProp.hasModel=true;var cfg=new ConfigNode();cfg.AddValue("doorTransformName","crewDoor");int before=Debug.logs.Count;h.OnLoad(cfg);h.OnAwake();Assert(Debug.logs.Count>before,"original shader failure not diagnosed");Assert(!model.GetComponentsInChildren<Mk33OriginalHatchMarker>(true).Any(m=>m.complete),"failed fallback shader authorized a cut");Assert(h.baseAwakeCalls==0,"failed original fallback reached native Awake");}finally{Shader.Missing.Clear();}});
        Scenario("native Awake failure keeps pressure plate physically sealed on later open callback",()=>{var f=Hatch(true,true,"nativeAwakeFailure",null,null,false,false,true);Assert(f.hatch.IsOpen,"dependency double did not expose partially opened native state");Assert(f.plate.gameObject.activeSelf&&f.seal.enabled,"pressure native failure left aperture uncapped");Assert(!f.part.GetComponent<ModuleFreeIva>().allowsUnbuckling,"pressure native failure did not disable local walking");f.seal.enabled=false;f.hatch.SetOpened(true);Assert(f.plate.gameObject.activeSelf&&f.seal.enabled,"unready pressure Open failed to restore physical cap");});
        Scenario("native Awake failure keeps original door sealed despite partial native open state",()=>{var f=Original(false,true,true,true,"nested",false,true,true);Assert(f.hatch.IsOpen,"original dependency double did not expose partial native state");Assert(f.door.gameObject.activeSelf&&f.seal.enabled,"original native failure left pressure seal disabled");Assert(!f.part.GetComponent<ModuleFreeIva>().allowsUnbuckling,"original native failure did not disable local walking");f.seal.enabled=false;f.hatch.SetOpened(true);Assert(f.door.gameObject.activeSelf&&f.seal.enabled,"unready original Open failed to restore physical cap");});
        Scenario("pressure Awake before load stays pending and later Start initializes without blocking walking",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("pressurePending");f.module.OnAwake();Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==0,"pending pressure Awake disabled walking or entered native initialization");f.module.OnLoad(f.valid);StartModule(f.module);Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==1,"loaded pressure did not initialize cleanly after pending Awake");});
        Scenario("original Awake before load stays pending and later Start preserves walking",()=>{var f=Lifecycle<Mk33FreeIvaHatch>("originalPending");f.module.OnAwake();Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==0,"pending original Awake disabled walking or entered native initialization");f.module.OnLoad(f.valid);StartModule(f.module);Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==1,"loaded original did not initialize after pending Awake");});
        Scenario("authored shell Awake before load does not turn pending state into failure",()=>{var f=Lifecycle<Mk33FreeIvaAuthoredShell>("authoredPending");f.module.OnAwake();Assert(f.walking.allowsUnbuckling,"pending authored validator disabled walking");f.module.OnLoad(f.valid);StartModule(f.module);f.module.OnAwake();Assert(f.walking.allowsUnbuckling&&f.model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>().complete,"valid authored shell remained blocked after pending Awake");});
        Scenario("pressure native registration waits for per-model FreeIVA cache",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("pressureNoCache",false);f.module.OnLoad(f.valid);f.module.OnAwake();StartModule(f.module);Assert(f.module.baseAwakeCalls==0&&f.walking.allowsUnbuckling,"pressure registered before native model cache or treated pending cache as failure");var cache=InternalModuleFreeIva.Register(f.model);StartModule(f.module);Tick(f.module);Assert(f.module.baseAwakeCalls==1&&cache.Hatches.Count(h=>h==f.module)==1,"pressure failed deferred native registration");});
        Scenario("original native registration waits for per-model FreeIVA cache",()=>{var f=Lifecycle<Mk33FreeIvaHatch>("originalNoCache",false);f.module.OnLoad(f.valid);f.module.OnAwake();StartModule(f.module);Assert(f.module.baseAwakeCalls==0&&f.walking.allowsUnbuckling,"original registered before native model cache or blocked pending cache");var cache=InternalModuleFreeIva.Register(f.model);StartModule(f.module);Tick(f.module);Assert(f.module.baseAwakeCalls==1&&cache.Hatches.Count(h=>h==f.module)==1,"original failed deferred native registration");});
        Scenario("ready pressure native Awake runs once across repeated lifecycle callbacks",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("pressureOnce");ReadyOriginal(f);f.module.OnAwake();StartModule(f.module);Tick(f.module);Assert(f.module.baseAwakeCalls==1&&InternalModuleFreeIva.GetForModel(f.model).Hatches.Count(h=>h==f.module)==1,"pressure duplicated native hatch registration");});
        Scenario("ready original native Awake runs once across repeated callbacks",()=>{var f=Lifecycle<Mk33FreeIvaHatch>("originalOnce");ReadyOriginal(f);f.module.OnAwake();StartModule(f.module);Tick(f.module);Assert(f.module.baseAwakeCalls==1&&InternalModuleFreeIva.GetForModel(f.model).Hatches.Count(h=>h==f.module)==1,"original duplicated native registration");});
        Scenario("genuine pressure load failure blocks walking and successful recovery releases its own block",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("pressureRecover");f.module.OnLoad(new ConfigNode());f.module.OnAwake();StartModule(f.module);Assert(!f.walking.allowsUnbuckling,"genuine pressure load failure did not block walking");ReadyOriginal(f);Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==1,"pressure recovery failed to release owned block");});
        Scenario("genuine authored shell failure can recover without retaining its walking block",()=>{var f=Lifecycle<Mk33FreeIvaAuthoredShell>("authoredRecover");var bad=new ConfigNode();bad.AddValue("sourceTransform","missingShell");f.module.OnLoad(bad);f.module.OnAwake();StartModule(f.module);Assert(!f.walking.allowsUnbuckling,"genuine authored failure did not block walking");ReadyOriginal(f);Assert(f.walking.allowsUnbuckling,"authored recovery retained its walking block");Assert(f.model.GetComponentsInChildren<MeshCollider>(true).Length==1,"authored revalidation duplicated existing physical colliders");});
        Scenario("recovery preserves an originally disabled unbuckling setting",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("configuredOff",true,false);f.module.OnAwake();Assert(!f.walking.allowsUnbuckling,"pending pressure enabled preexisting disabled walking");f.module.OnLoad(new ConfigNode());StartModule(f.module);ReadyOriginal(f);Assert(!f.walking.allowsUnbuckling,"recovering own block overwrote original allowsUnbuckling=false");});
        Scenario("two failing pressure owners cannot prematurely release each other's part block",()=>{var first=Lifecycle<Mk33FreeIvaPressureHatch>("firstOwner");var second=Lifecycle<Mk33FreeIvaPressureHatch>("secondOwner",true,true,first.part,first.model);first.module.OnLoad(new ConfigNode());second.module.OnLoad(new ConfigNode());StartModule(first.module);StartModule(second.module);Assert(!first.walking.allowsUnbuckling,"multiple failures did not block shared part");ReadyOriginal(first);Assert(!first.walking.allowsUnbuckling,"first recovery released second owner's active block");ReadyOriginal(second);Assert(first.walking.allowsUnbuckling,"all owners recovered but walking stayed blocked");});
        Scenario("geometry Awake before load remains pending then builds a ready collision shell",()=>{var f=Lifecycle<Mk33FreeIvaGeometry>("geometryPending");f.module.OnAwake();Assert(f.walking.allowsUnbuckling,"geometry pending Awake disabled walking");f.module.OnLoad(f.valid);StartModule(f.module);var marker=f.model.transform.Find("Mk33Shell").GetComponent<Mk33ColliderMarker>();Assert(marker.complete&&marker.sourceCount==1&&f.walking.allowsUnbuckling,"ready geometry shell stayed blocked");Assert(f.model.GetComponentsInChildren<MeshCollider>(true).Length==1,"geometry source failed to produce shell collider");});
        Scenario("geometry Start before load does not latch an unbuckling block",()=>{var f=Lifecycle<Mk33FreeIvaGeometry>("geometryStartPending");f.module.OnAwake();StartModule(f.module);Assert(f.walking.allowsUnbuckling,"unattempted geometry load was treated as failure");f.module.OnLoad(f.valid);Tick(f.module);Assert(f.walking.allowsUnbuckling,"later successful geometry load failed to stay unblocked");});
        Scenario("genuine geometry failure blocks then successful build releases its own block",()=>{var f=Lifecycle<Mk33FreeIvaGeometry>("geometryRecover");var bad=new ConfigNode();bad.AddValue("sourceTransform","missingMesh");f.module.OnLoad(bad);StartModule(f.module);Assert(!f.walking.allowsUnbuckling,"attempted geometry failure did not block walking");f.module.OnLoad(f.valid);Tick(f.module);Assert(f.walking.allowsUnbuckling,"successful geometry build failed to release owned block");});
        Scenario("geometry recovery preserves configured unbuckling false",()=>{var f=Lifecycle<Mk33FreeIvaGeometry>("geometryConfiguredOff",true,false);f.module.OnLoad(new ConfigNode());StartModule(f.module);Assert(!f.walking.allowsUnbuckling,"geometry failure changed configured policy");f.module.OnLoad(f.valid);Tick(f.module);Assert(!f.walking.allowsUnbuckling,"geometry recovery overwrote configured false policy");});
        Scenario("genuine original load failure can recover and restore configured walking",()=>{var f=Lifecycle<Mk33FreeIvaHatch>("originalRecover");var bad=f.valid.CreateCopy();bad.GetNode("DoorCollider").SetValue("shape","UnknownShape");f.module.OnLoad(bad);StartModule(f.module);Assert(!f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==0,"failed original load did not own walking block before native Awake");ReadyOriginal(f);Assert(f.walking.allowsUnbuckling&&f.module.baseAwakeCalls==1,"original successful retry did not release owned block");});
        Scenario("original recovery preserves configured unbuckling false",()=>{var f=Lifecycle<Mk33FreeIvaHatch>("originalConfiguredOff",true,false);var bad=f.valid.CreateCopy();bad.GetNode("DoorCollider").SetValue("shape","UnknownShape");f.module.OnLoad(bad);StartModule(f.module);ReadyOriginal(f);Assert(!f.walking.allowsUnbuckling,"original recovery overwrote configured false policy");});
        Scenario("all four real module writers share walking-block ownership without early release",()=>{var pressure=Lifecycle<Mk33FreeIvaPressureHatch>("fourPressure");var original=Lifecycle<Mk33FreeIvaHatch>("fourOriginal",true,true,pressure.part);var geometry=Lifecycle<Mk33FreeIvaGeometry>("fourGeometry",true,true,pressure.part);var authored=Lifecycle<Mk33FreeIvaAuthoredShell>("fourAuthored",true,true,pressure.part);var badOriginal=original.valid.CreateCopy();badOriginal.GetNode("DoorCollider").SetValue("shape","UnknownShape");pressure.module.OnLoad(new ConfigNode());original.module.OnLoad(badOriginal);geometry.module.OnLoad(new ConfigNode());authored.module.OnLoad(new ConfigNode());StartModule(pressure.module);StartModule(original.module);StartModule(geometry.module);StartModule(authored.module);Assert(!pressure.walking.allowsUnbuckling,"four real failed writers did not block shared part");ReadyOriginal(pressure);Assert(!pressure.walking.allowsUnbuckling,"pressure cleared another writer's block");ReadyOriginal(original);Assert(!pressure.walking.allowsUnbuckling,"original cleared shell writers' blocks");ReadyOriginal(geometry);Assert(!pressure.walking.allowsUnbuckling,"geometry cleared authored writer's block");ReadyOriginal(authored);Assert(pressure.walking.allowsUnbuckling,"last real writer recovered without restoring original true policy");});
        Scenario("ready model cache cannot trigger pressure native Awake before Start",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("pressureStrictStart");f.module.OnLoad(f.valid);f.module.OnAwake();Assert(f.module.baseAwakeCalls==0&&f.walking.allowsUnbuckling,"pressure initialized native module during early Awake");StartModule(f.module);Assert(f.module.baseAwakeCalls==1,"pressure did not initialize at safe Start boundary");});
        Scenario("ready model cache cannot trigger original native Awake before Start",()=>{var f=Lifecycle<Mk33FreeIvaHatch>("originalStrictStart");f.module.OnLoad(f.valid);f.module.OnAwake();Assert(f.module.baseAwakeCalls==0&&f.walking.allowsUnbuckling,"original initialized native module during early Awake");StartModule(f.module);Assert(f.module.baseAwakeCalls==1,"original did not initialize at Start");});
        Scenario("walking gate rebinds replacement module and preserves its true baseline",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("replaceWalkingTrue");f.module.OnLoad(new ConfigNode());StartModule(f.module);var old=f.walking;f.part.gameObject.RemoveComponent(old);f.part.Modules.Remove(old);var replacement=Module<ModuleFreeIva>(f.part);replacement.allowsUnbuckling=true;Tick(f.module);Assert(!replacement.allowsUnbuckling,"new attached walking module was not protected");ReadyOriginal(f);Assert(replacement.allowsUnbuckling,"owned block did not restore replacement's true baseline");});
        Scenario("walking gate rebinds replacement module without enabling configured false",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("replaceWalkingFalse");f.module.OnLoad(new ConfigNode());StartModule(f.module);var old=f.walking;f.part.gameObject.RemoveComponent(old);f.part.Modules.Remove(old);var replacement=Module<ModuleFreeIva>(f.part);replacement.allowsUnbuckling=false;Tick(f.module);ReadyOriginal(f);Assert(!replacement.allowsUnbuckling,"replacement module's false baseline was overwritten");});
        Scenario("owned releases while walking module is absent do not remain latched on replacement",()=>{var f=Lifecycle<Mk33FreeIvaPressureHatch>("absentWalking");f.module.OnLoad(new ConfigNode());StartModule(f.module);var old=f.walking;f.part.gameObject.RemoveComponent(old);f.part.Modules.Remove(old);ReadyOriginal(f);var replacement=Module<ModuleFreeIva>(f.part);replacement.allowsUnbuckling=true;Tick(f.module);Assert(replacement.allowsUnbuckling,"released owner was latched across missing/replaced walking module");});
        Scenario("destroying one owner retains other blocks and final owner cleanup restores policy",()=>{var first=Lifecycle<Mk33FreeIvaPressureHatch>("destroyFirstOwner");var second=Lifecycle<Mk33FreeIvaPressureHatch>("destroySecondOwner",true,true,first.part,first.model);first.module.OnLoad(new ConfigNode());second.module.OnLoad(new ConfigNode());StartModule(first.module);StartModule(second.module);Assert(!first.walking.allowsUnbuckling,"owner cleanup scenario did not establish blocked part");first.module.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(first.module,null);Assert(!first.walking.allowsUnbuckling,"one destroyed owner released another owner's block");second.module.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(second.module,null);Assert(first.walking.allowsUnbuckling,"final destroyed owner failed to restore configured true policy");});
        Scenario("failed original destruction releases only its own owner and disabling keeps failures latched",()=>{var pressure=Lifecycle<Mk33FreeIvaPressureHatch>("destroyPressurePeer");var original=Lifecycle<Mk33FreeIvaHatch>("destroyOriginalOwner",true,true,pressure.part);var bad=original.valid.CreateCopy();bad.GetNode("DoorCollider").SetValue("shape","UnknownShape");pressure.module.OnLoad(new ConfigNode());original.module.OnLoad(bad);StartModule(pressure.module);StartModule(original.module);foreach(var module in new InternalModule[]{pressure.module,original.module}){var disable=module.GetType().GetMethod("OnDisable",BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public);if(disable!=null)disable.Invoke(module,null);}Assert(!pressure.walking.allowsUnbuckling,"disable callback released a true failure");original.module.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(original.module,null);Assert(!pressure.walking.allowsUnbuckling,"destroyed original owner released pressure owner's block");pressure.module.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(pressure.module,null);Assert(pressure.walking.allowsUnbuckling,"final pressure cleanup did not restore policy after original destruction");});
        Scenario("healthy pressure and original destruction never rewrite an external walking policy",()=>{var pressure=Lifecycle<Mk33FreeIvaPressureHatch>("healthyPressureDestroy");ReadyOriginal(pressure);pressure.walking.allowsUnbuckling=false;pressure.module.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(pressure.module,null);Assert(!pressure.walking.allowsUnbuckling,"healthy pressure destruction rewrote unrelated policy");var original=Lifecycle<Mk33FreeIvaHatch>("healthyOriginalDestroy",true,true,pressure.part);ReadyOriginal(original);original.module.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(original.module,null);Assert(!pressure.walking.allowsUnbuckling,"healthy original destruction rewrote unrelated policy");});
        ClassicHatchScenarios();
        ImportedShellScenarios();
        CentralDoorScenarios();
        var report=new {in_game_tested=false,unity_physx_executed=false,native_freeiva_executed=false,method="Compile and execute entire exact production C# pressure-hatch, walking-gate, geometry-builder, authored-shell validator and original-door adapter sources with deterministic dependency doubles. Exercises custom state, geometry generation and physical-connection checks; native Open semantics reduced to documented branches. Mirrors the evidenced KSPCF forced-convex assignment before imported-shell validation without executing the actual parser.",passed_count=passed.Count,scenarios=passed};
        var json=JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true});if(args.Length>0)File.WriteAllText(args[0],json+"\n");Console.WriteLine(json);
    }
}
