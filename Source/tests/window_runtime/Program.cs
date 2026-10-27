// SPDX-License-Identifier: GPL-2.0-or-later
// Executes the exact production window helper with dependency doubles.
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
        public InternalModel model;
        public Mk33FreeIvaWindowMask helper;
        public MeshRenderer glass;
        public MeshFilter filter;
        public InternalModuleFreeIva native;
        public ConfigNode config;
        public Transform Mask {get{return model.transform.Find("Mk33WindowDepthMask");}}
        public MeshRenderer Depth {get{return Mask.GetComponent<MeshRenderer>();}}
    }
    static void Assert(bool b,string message){if(!b)throw new Exception(message);}
    static void Call(object o,string name){o.GetType().GetMethod(name,BindingFlags.Instance|BindingFlags.NonPublic).Invoke(o,null);}
    static void Tick(Fixture f){Call(f.helper,"LateUpdate");}
    static void Check(string name,Action test)
    {
        HighLogic.LoadedSceneIsFlight=true;
        CameraManager.Instance=new CameraManager();
        Utils.Throw=false;Utils.Shader=new Shader{name="DepthMask_Culling"};
        test();passed.Add(name);Console.WriteLine("PASS "+name);
    }
    static Fixture New(bool load=true,bool register=true)
    {
        var f=new Fixture();f.model=new GameObject("internal").AddComponent<InternalModel>();f.model.internalName="windowTest";
        var modelRoot=new GameObject("model");modelRoot.transform.SetParent(f.model.transform,false);
        var meshRoot=new GameObject("originalIva");meshRoot.transform.SetParent(modelRoot.transform,false);
        var glass=new GameObject("windows");glass.transform.SetParent(meshRoot.transform,false);
        f.filter=glass.AddComponent<MeshFilter>();f.filter.sharedMesh=new Mesh{vertices=new[]{new Vector3(-1,-1,2),new Vector3(1,-1,2),new Vector3(1,1,2),new Vector3(-1,1,2)},triangles=new[]{0,1,2,0,2,3}};
        f.glass=glass.AddComponent<MeshRenderer>();f.glass.sharedMaterial=new Material(new Shader{name="KSP/Alpha/Unlit Transparent"}){renderQueue=1999,color=new Color(1,1,1,.3f)};
        var wrapper=new GameObject("windowHelper");wrapper.transform.SetParent(f.model.transform,false);
        f.helper=wrapper.AddComponent<Mk33FreeIvaWindowMask>();f.helper.internalModel=f.model;
        f.helper.internalProp=wrapper.AddComponent<InternalProp>();f.helper.internalProp.internalModel=f.model;
        if(register)f.native=InternalModuleFreeIva.Register(f.model);
        f.config=new ConfigNode();f.config.AddValue("sourceTransform","windows");
        if(load)f.helper.OnLoad(f.config);
        return f;
    }
    static void Ready(Fixture f)
    {
        Call(f.helper,"Start");
        Assert(f.Depth.enabled && f.Depth.sharedMaterial.shader==Utils.Shader,"depth shader not ready");
        Assert(f.Depth.sharedMaterial.renderQueue==998,"mask does not precede promoted IVA queue999");
        Assert(f.native.internalDepthMask==f.Mask,"native mask not bound");
    }
    static void Main(string[] args)
    {
        Check("Load creates an invisible placeholder, never a colour copy",()=>{var f=New();Assert(!f.Depth.enabled && f.Depth.sharedMaterial==null,"visible/coloured fallback created");});
        Check("Runtime uses an isolated native shader at queue998",()=>{var f=New();var glassMaterial=f.glass.sharedMaterial;Ready(f);Assert(f.Depth.sharedMaterial!=glassMaterial && f.glass.sharedMaterial==glassMaterial,"shared source material modified");Assert(f.glass.sharedMaterial.renderQueue==1999,"glass queue altered");});
        Check("The original source mesh and material are not mutated",()=>{var f=New(false);var mesh=f.filter.sharedMesh;var vertices=mesh.vertices;var triangles=mesh.triangles;var material=f.glass.sharedMaterial;f.helper.OnLoad(f.config);Ready(f);Assert(f.filter.sharedMesh==mesh && mesh.vertices.SequenceEqual(vertices) && mesh.triangles.SequenceEqual(triangles),"source mesh changed");Assert(f.glass.sharedMaterial==material && f.glass.enabled,"source glass changed");});
        Check("Every source triangle has both depth windings",()=>{var f=New();var s=f.filter.sharedMesh.triangles;var d=f.Mask.GetComponent<MeshFilter>().sharedMesh.triangles;Assert(d.Length==s.Length*2,"incorrect mask count");for(int i=0;i<s.Length;i+=3)Assert(d[i]==s[i]&&d[i+1]==s[i+1]&&d[i+2]==s[i+2]&&d[s.Length+i]==s[i]&&d[s.Length+i+1]==s[i+2]&&d[s.Length+i+2]==s[i+1],"winding mismatch");});
        Check("Complete nested source transforms are baked relative to the IVA",()=>{var f=New(false);f.model.transform.localPosition=new Vector3(100,200,300);f.filter.transform.parent.localPosition=new Vector3(2,3,4);f.filter.transform.localPosition=new Vector3(1,-2,1);f.filter.transform.localScale=new Vector3(-2,3,.5f);f.helper.OnLoad(f.config);var p=f.Mask.GetComponent<MeshFilter>().sharedMesh.vertices[0];Assert((p-new Vector3(5,-2,6)).magnitude<.0001,"incorrect nested source transform");});
        Check("Mask construction adds no physical collider",()=>{var f=New();Ready(f);Assert(f.Mask.GetComponentsInChildren<Collider>(true).Length==0,"mask interferes with movement");});
        Check("Native OnLoad material replacement is repaired without mutating its singleton",()=>{var f=New();var global=new Material(Utils.Shader){renderQueue=1000};f.Depth.sharedMaterial=global;Ready(f);Assert(f.Depth.sharedMaterial!=global && global.renderQueue==1000,"native singleton modified");});
        Check("Missing or stale native mask reference is rebound",()=>{var f=New();f.native.internalDepthMask=new GameObject("staleMask").transform;Ready(f);f.native.internalDepthMask=null;Tick(f);Assert(f.native.internalDepthMask==f.Mask,"late binding repair failed");});
        Check("An unrelated configured mask is not hijacked",()=>{var f=New();var other=new GameObject("otherMask").transform;f.native.internalDepthMask=other;f.native.internalDepthMaskName="otherMask";var errors=Debug.errorCount;Tick(f);Tick(f);Assert(f.native.internalDepthMask==other && !f.Depth.enabled && Debug.errorCount==errors+1,"configuration guard failed");f.native.internalDepthMaskName="Mk33WindowDepthMask";Ready(f);});
        Check("Start before OnLoad and native cache readiness is harmless",()=>{var f=New(false,false);Call(f.helper,"Start");f.helper.OnLoad(f.config);Tick(f);Assert(!f.Depth.enabled,"enabled without native module");f.native=InternalModuleFreeIva.Register(f.model);Ready(f);});
        Check("Late runtime instance rediscovers serialized marker with cleared private fields",()=>{var f=New();var wrapper=new GameObject("clonedHelper");wrapper.transform.SetParent(f.model.transform,false);f.helper=wrapper.AddComponent<Mk33FreeIvaWindowMask>();f.helper.internalProp=wrapper.AddComponent<InternalProp>();f.helper.internalProp.internalModel=f.model;Ready(f);});
        Check("Repeated OnLoad retains exactly one complete mask",()=>{var f=New();var mask=f.Mask;f.helper.OnLoad(f.config);Ready(f);Assert(f.Mask==mask&&f.model.transform.children.Count(t=>t.name=="Mk33WindowDepthMask")==1,"duplicated mask");});
        Check("Camera transitions match native modes and preserve external mask",()=>{var f=New();var external=new GameObject("originalExternalMask");external.SetActive(false);f.native.externalDepthMask=external.transform;Ready(f);CameraManager.Instance.currentCameraMode=CameraManager.CameraMode.Flight;Tick(f);Assert(!f.Mask.gameObject.activeSelf,"mask visible in Flight");CameraManager.Instance.currentCameraMode=CameraManager.CameraMode.IVA;Tick(f);Assert(f.Mask.gameObject.activeSelf,"mask hidden in IVA");CameraManager.Instance.currentCameraMode=CameraManager.CameraMode.Internal;Tick(f);Assert(f.Mask.gameObject.activeSelf,"mask hidden in Internal camera");Assert(f.native.externalDepthMask==external.transform&&!external.activeSelf,"external mask changed");});
        Check("Creation after Flight camera event still sets correct visibility",()=>{CameraManager.Instance.currentCameraMode=CameraManager.CameraMode.Flight;var f=New();Ready(f);Assert(!f.Mask.gameObject.activeSelf,"late instance ignored current camera mode");});
        Check("Null camera manager does not break loading or material initialization",()=>{CameraManager.Instance=null;var f=New();Ready(f);});
        Check("Missing shader never renders original colour and recovers when ready",()=>{var f=New();Utils.Shader=null;var errors=Debug.errorCount;Tick(f);Tick(f);Assert(!f.Depth.enabled&&f.Depth.sharedMaterial==null&&Debug.errorCount==errors+1,"missing shader fallback/spam");Utils.Shader=new Shader{name="DepthMask_Culling"};Ready(f);});
        Check("Unavailable asset loader is retried instead of aborting IVA compilation",()=>{var f=New();Utils.Throw=true;Tick(f);Assert(!f.Depth.enabled,"renderer enabled without shader");Utils.Throw=false;Ready(f);});
        Check("Unsupported shader disables only the added renderer",()=>{var f=New();Ready(f);Utils.Shader.isSupported=false;Tick(f);Assert(!f.Depth.enabled&&f.glass.enabled,"unsupported shader affects source");Utils.Shader.isSupported=true;Ready(f);});
        Check("Late colour-material replacement is repaired before rendering",()=>{var f=New();Ready(f);var material=f.Depth.sharedMaterial;f.Depth.sharedMaterial=f.glass.sharedMaterial;Tick(f);Assert(f.Depth.sharedMaterial==material,"late sharedMaterial not repaired");});
        Check("Late queue, shader, layer and renderer changes are repaired locally",()=>{var f=New();Ready(f);f.Depth.sharedMaterial.renderQueue=3000;f.Depth.sharedMaterial.shader=new Shader{name="badColourShader"};f.Depth.gameObject.layer=0;f.Depth.enabled=false;f.Depth.shadowCastingMode=UnityEngine.Rendering.ShadowCastingMode.On;f.Depth.receiveShadows=true;Tick(f);Assert(f.Depth.sharedMaterial.renderQueue==998&&f.Depth.sharedMaterial.shader==Utils.Shader&&f.Depth.gameObject.layer==20&&f.Depth.enabled&&!f.Depth.receiveShadows&&f.Depth.shadowCastingMode==UnityEngine.Rendering.ShadowCastingMode.Off,"runtime invariant drift");});
        Check("Stable frame updates allocate no additional materials",()=>{var f=New();Ready(f);var count=Material.Created;for(int i=0;i<100;i++)Tick(f);Assert(Material.Created==count,"per-frame material allocation");});
        Check("Two IVA instances own different materials and state",()=>{var a=New();var b=New();Ready(a);Ready(b);Assert(a.Depth.sharedMaterial!=b.Depth.sharedMaterial,"material leaked across models");a.Depth.sharedMaterial.renderQueue=3000;Assert(b.Depth.sharedMaterial.renderQueue==998,"cross-model mutation");});
        Check("Destruction releases only the helper's owned material",()=>{var f=New();Ready(f);var material=f.Depth.sharedMaterial;Call(f.helper,"OnDestroy");Assert(UnityEngine.Object.Destroyed.Contains(material)&&!UnityEngine.Object.Destroyed.Contains(f.glass.sharedMaterial),"wrong material released");});
        Check("Missing source reports a bounded error and leaves original glass",()=>{var f=New(false);f.config=new ConfigNode();f.config.AddValue("sourceTransform","missing");f.helper.OnLoad(f.config);Assert(f.Mask==null&&f.glass.enabled,"missing-source failure altered original");});
        Check("Invalid mesh indices are rejected before creating a mask",()=>{var f=New(false);f.filter.sharedMesh.triangles=new[]{0,1,100};f.helper.OnLoad(f.config);Assert(f.Mask==null,"invalid index accepted");});
        Check("Empty source is rejected before creating a mask",()=>{var f=New(false);f.filter.sharedMesh.triangles=new int[0];f.helper.OnLoad(f.config);Assert(f.Mask==null,"empty source accepted");});
        Check("Non-finite source geometry is rejected before creating a mask",()=>{var f=New(false);f.filter.sharedMesh.vertices=new[]{new Vector3(Single.NaN,0,0),new Vector3(1,0,0),new Vector3(0,1,0)};f.filter.sharedMesh.triangles=new[]{0,1,2};f.helper.OnLoad(f.config);Assert(f.Mask==null,"NaN geometry accepted");});
        Check("Conflicting generated-name object is left untouched",()=>{var f=New(false);var collision=new GameObject("Mk33WindowDepthMask");collision.transform.SetParent(f.model.transform,false);f.helper.OnLoad(f.config);Tick(f);Assert(collision.GetComponents<MeshRenderer>().Length==0,"conflicting object overwritten");});
        Check("Missing INTERNAL context reports instead of throwing",()=>{var m=new GameObject("badHelper").AddComponent<Mk33FreeIvaWindowMask>();m.OnLoad(new ConfigNode());Call(m,"Start");});
        Check("Loading scene does not create runtime materials or touch native camera state",()=>{var f=New();HighLogic.LoadedSceneIsFlight=false;Call(f.helper,"Start");Assert(!f.Depth.enabled&&f.Depth.sharedMaterial==null&&f.native.internalDepthMask==null,"flight state used while loading");});
        File.WriteAllText(args[0],JsonSerializer.Serialize(new{passed=passed.Count,failed=0,scenarios=passed,in_game_tested=false},new JsonSerializerOptions{WriteIndented=true})+"\n");
    }
}
