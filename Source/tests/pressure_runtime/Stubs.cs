// SPDX-License-Identifier: GPL-2.0-or-later
// Deliberately small dependency doubles. These do not execute Unity, PhysX,
// ModuleManager, KSP's asset/INTERNAL loader, or native FreeIVA coroutines.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

[AttributeUsage(AttributeTargets.Field)] public sealed class KSPField : Attribute { }
[AttributeUsage(AttributeTargets.Assembly)] public sealed class KSPAssembly : Attribute {public KSPAssembly(string name,int major,int minor){}}
[AttributeUsage(AttributeTargets.Assembly)] public sealed class KSPAssemblyDependency : Attribute {public KSPAssemblyDependency(string name,int major,int minor){}}
public sealed class ConfigNode
{
    public string name; public ConfigNode(string name=""){this.name=name;}
    readonly List<KeyValuePair<string, string>> values = new List<KeyValuePair<string, string>>();
    readonly List<ConfigNode> nodes=new List<ConfigNode>();
    public void AddValue(string key, object value) { values.Add(new KeyValuePair<string, string>(key, Convert.ToString(value, CultureInfo.InvariantCulture))); }
    public string GetValue(string key) { return values.Where(p => p.Key == key).Select(p => p.Value).FirstOrDefault(); }
    public string[] GetValues(string key) { return values.Where(p => p.Key == key).Select(p => p.Value).ToArray(); }
    public bool HasValue(string key) { return values.Any(p => p.Key == key); }
    public void RemoveValues(string key) { values.RemoveAll(p => p.Key == key); }
    public ConfigNode CreateCopy() { var n = new ConfigNode(name); foreach (var p in values) n.AddValue(p.Key, p.Value);foreach(var child in nodes)n.nodes.Add(child.CreateCopy()); return n; }
    public ConfigNode AddNode(string name){var n=new ConfigNode(name);nodes.Add(n);return n;}
    public void AddNode(ConfigNode node){nodes.Add(node);}
    public ConfigNode GetNode(string name){return nodes.FirstOrDefault(n=>n.name==name);}
    public ConfigNode[] GetNodes(string name){return nodes.Where(n=>n.name==name).ToArray();}
    public void RemoveNodes(string name){nodes.RemoveAll(n=>n.name==name);}
    public void SetValue(string name,object value,bool createIfNotFound=false){RemoveValues(name);AddValue(name,value);}
    public bool TryGetValue(string key, ref UnityEngine.Quaternion value) { var s=GetValue(key);if(s==null)return false;var a=s.Split(',').Select(x=>Single.Parse(x,CultureInfo.InvariantCulture)).ToArray();value=new UnityEngine.Quaternion(a[0],a[1],a[2],a[3]);return true;}
    public bool TryGetValue(string key, ref UnityEngine.Vector3 value) { var s=GetValue(key); if(s==null)return false; var a=s.Split(',').Select(x=>Single.Parse(x,CultureInfo.InvariantCulture)).ToArray();value=new UnityEngine.Vector3(a[0],a[1],a[2]);return true; }
    public bool TryGetValue(string key, ref string value) { var s=GetValue(key); if(s==null)return false; value=s; return true; }
    public bool TryGetValue(string key, ref bool value) { var s=GetValue(key); if(s==null)return false; value=Boolean.Parse(s); return true; }
    public bool TryGetValue(string key, ref float value) { var s=GetValue(key); if(s==null)return false; value=Single.Parse(s,CultureInfo.InvariantCulture); return true; }
}
namespace UnityEngine
{
    [AttributeUsage(AttributeTargets.Field)] public sealed class SerializeField : Attribute { }
    public class Component
    {
        public GameObject gameObject;
        public Transform transform { get { return gameObject.transform; } }
        public string name { get { return gameObject.name; } set { gameObject.name=value; } }
        public int GetInstanceID(){return System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(this);}
        public T GetComponent<T>() where T:class { return gameObject.GetComponent<T>(); }
        public T[] GetComponents<T>() where T:class {return gameObject.GetComponents<T>();}
        public T[] GetComponentsInChildren<T>(bool includeInactive=false) where T:class { return gameObject.GetComponentsInChildren<T>(includeInactive); }
    }
    public class MonoBehaviour : Component { public bool enabled=true; }
    public sealed class GameObject
    {
        public string name; public int layer; public bool activeSelf=true;
        public readonly Transform transform;
        readonly List<Component> components=new List<Component>();
        public bool activeInHierarchy { get { return activeSelf && (transform.parent==null || transform.parent.gameObject.activeInHierarchy); } }
        public GameObject(string n) { name=n; transform=new Transform(); transform.gameObject=this; components.Add(transform); }
        public T AddComponent<T>() where T:Component,new() { var c=new T(); c.gameObject=this; components.Add(c); return c; }
        public T GetComponent<T>() where T:class { return components.OfType<T>().FirstOrDefault(); }
        public T[] GetComponents<T>() where T:class {return components.OfType<T>().ToArray();}
        public T[] GetComponentsInChildren<T>(bool includeInactive=false) where T:class
        {
            var a=new List<T>();
            if(includeInactive || activeInHierarchy) a.AddRange(components.OfType<T>());
            foreach(var c in transform.children) a.AddRange(c.gameObject.GetComponentsInChildren<T>(includeInactive));
            return a.ToArray();
        }
        public void SetActive(bool value) { activeSelf=value; }
        public void RemoveComponent(Component component){components.Remove(component);}
    }
    public sealed class Transform : Component
    {
        public Transform parent;
        public readonly List<Transform> children=new List<Transform>();
        public Vector3 localPosition; public Quaternion localRotation=Quaternion.identity; public Vector3 localScale=Vector3.one;
        public Matrix4x4 localToWorldMatrix {get{var local=Matrix4x4.TRS(localPosition,localRotation,localScale);return parent==null?local:parent.localToWorldMatrix*local;}}
        public Matrix4x4 worldToLocalMatrix {get{return localToWorldMatrix.inverse;}}
        public Vector3 position { get { return parent==null?localPosition:parent.TransformPoint(localPosition); } set { localPosition=parent==null?value:parent.InverseTransformPoint(value); } }
        public Quaternion rotation { get { return parent==null?localRotation:parent.rotation*localRotation; } set { localRotation=parent==null?value:Quaternion.Inverse(parent.rotation)*value; } }
        public Vector3 lossyScale { get { return parent==null?localScale:Vector3.Scale(parent.lossyScale,localScale); } }
        public Vector3 TransformPoint(Vector3 p) { var q=localPosition+localRotation*Vector3.Scale(localScale,p);return parent==null?q:parent.TransformPoint(q); }
        public Vector3 InverseTransformPoint(Vector3 p) { var q=parent==null?p:parent.InverseTransformPoint(p);q=Quaternion.Inverse(localRotation)*(q-localPosition);return new Vector3(q.x/localScale.x,q.y/localScale.y,q.z/localScale.z); }
        public void SetParent(Transform value,bool worldPositionStays) { var oldPosition=position;var oldRotation=rotation;var oldScale=lossyScale;if(parent!=null)parent.children.Remove(this); parent=value; if(value!=null)value.children.Add(this);if(worldPositionStays){position=oldPosition;rotation=oldRotation;var target=parent==null?Vector3.one:parent.lossyScale;localScale=new Vector3(oldScale.x/target.x,oldScale.y/target.y,oldScale.z/target.z);} }
        public int childCount { get { return children.Count; } }
        public Transform GetChild(int index) { return children[index]; }
        public Transform Find(string n) { return children.FirstOrDefault(c=>c.name==n); }
        public bool IsChildOf(Transform other) { for(var p=this;p!=null;p=p.parent)if(p==other)return true; return false; }
    }
    public struct Vector3
    {
        public float x,y,z; public Vector3(float a,float b,float c) { x=a;y=b;z=c; }
        public static Vector3 zero { get { return new Vector3(0,0,0); } }
        public static Vector3 one { get { return new Vector3(1,1,1); } }
        public static Vector3 up { get { return new Vector3(0,1,0); } }
        public static Vector3 operator+(Vector3 a,Vector3 b){return new Vector3(a.x+b.x,a.y+b.y,a.z+b.z);}
        public static Vector3 operator-(Vector3 a,Vector3 b){return new Vector3(a.x-b.x,a.y-b.y,a.z-b.z);}
        public static Vector3 operator*(Vector3 a,float b){return new Vector3(a.x*b,a.y*b,a.z*b);}
        public static Vector3 operator/(Vector3 a,float b){return new Vector3(a.x/b,a.y/b,a.z/b);}
        public static Vector3 Scale(Vector3 a,Vector3 b){return new Vector3(a.x*b.x,a.y*b.y,a.z*b.z);}
        public float magnitude {get{return (float)Math.Sqrt(x*x+y*y+z*z);}}
        public float sqrMagnitude {get{return x*x+y*y+z*z;}}
        public Vector3 normalized {get{return this/magnitude;}}
        public static Vector3 forward {get{return new Vector3(0,0,1);}}
        public static float Dot(Vector3 a,Vector3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
    }
    public struct Vector4 { public float x,y,z,w; public Vector4(float a,float b,float c,float d){x=a;y=b;z=c;w=d;} }
    public struct Vector2 { public float x,y; public Vector2(float a,float b){x=a;y=b;} }
    public struct Quaternion
    {
        public float x,y,z,w; public Quaternion(float a,float b,float c,float d){x=a;y=b;z=c;w=d;}
        public static Quaternion identity { get { return new Quaternion(0,0,0,1); } }
        static System.Numerics.Quaternion N(Quaternion q){return new System.Numerics.Quaternion(q.x,q.y,q.z,q.w);}
        static Quaternion U(System.Numerics.Quaternion q){return new Quaternion(q.X,q.Y,q.Z,q.W);}
        public static Quaternion LookRotation(Vector3 forward,Vector3 up)
        {
            var f=System.Numerics.Vector3.Normalize(new System.Numerics.Vector3(forward.x,forward.y,forward.z));var u=new System.Numerics.Vector3(up.x,up.y,up.z);
            var r=System.Numerics.Vector3.Normalize(System.Numerics.Vector3.Cross(u,f));u=System.Numerics.Vector3.Cross(f,r);
            var m=new System.Numerics.Matrix4x4(r.X,r.Y,r.Z,0,u.X,u.Y,u.Z,0,f.X,f.Y,f.Z,0,0,0,0,1);return U(System.Numerics.Quaternion.CreateFromRotationMatrix(m));
        }
        public static Quaternion Inverse(Quaternion q){return U(System.Numerics.Quaternion.Inverse(N(q)));}
        public static Quaternion operator*(Quaternion a,Quaternion b){return U(N(a)*N(b));}
        public static Vector3 operator*(Quaternion q,Vector3 v){var p=System.Numerics.Vector3.Transform(new System.Numerics.Vector3(v.x,v.y,v.z),N(q));return new Vector3(p.X,p.Y,p.Z);}
    }
    public struct Color { public float r,g,b,a; public Color(float x,float y,float z,float v){r=x;g=y;b=z;a=v;} }
    public static class Mathf { public const float PI=(float)Math.PI; public static float Abs(float x){return Math.Abs(x);} public static float Cos(float x){return (float)Math.Cos(x);} public static float Sin(float x){return (float)Math.Sin(x);} }
    public struct Matrix4x4
    {
        System.Numerics.Matrix4x4 value;public Matrix4x4(System.Numerics.Matrix4x4 m){value=m;}
        public static Matrix4x4 TRS(Vector3 p,Quaternion q,Vector3 s){var scale=System.Numerics.Matrix4x4.CreateScale(s.x,s.y,s.z);var rotation=System.Numerics.Matrix4x4.CreateFromQuaternion(new System.Numerics.Quaternion(q.x,q.y,q.z,q.w));var translation=System.Numerics.Matrix4x4.CreateTranslation(p.x,p.y,p.z);return new Matrix4x4(scale*rotation*translation);}
        public static Matrix4x4 operator*(Matrix4x4 a,Matrix4x4 b){return new Matrix4x4(b.value*a.value);}
        public Matrix4x4 inverse {get{System.Numerics.Matrix4x4 result;System.Numerics.Matrix4x4.Invert(value,out result);return new Matrix4x4(result);}}
        public float determinant {get{return value.GetDeterminant();}}
        public Matrix4x4 transpose {get{return new Matrix4x4(System.Numerics.Matrix4x4.Transpose(value));}}
        public Vector3 MultiplyVector(Vector3 v){var p=System.Numerics.Vector3.TransformNormal(new System.Numerics.Vector3(v.x,v.y,v.z),value);return new Vector3(p.X,p.Y,p.Z);}
        public Vector3 MultiplyPoint3x4(Vector3 v){var p=System.Numerics.Vector3.Transform(new System.Numerics.Vector3(v.x,v.y,v.z),value);return new Vector3(p.X,p.Y,p.Z);}
    }
    public struct Bounds
    {
        public Vector3 center,size;public Bounds(Vector3 c,Vector3 s){center=c;size=s;}
        public void Encapsulate(Vector3 p){var lo=center-size/2;var hi=center+size/2;lo=new Vector3(Math.Min(lo.x,p.x),Math.Min(lo.y,p.y),Math.Min(lo.z,p.z));hi=new Vector3(Math.Max(hi.x,p.x),Math.Max(hi.y,p.y),Math.Max(hi.z,p.z));center=(lo+hi)/2;size=hi-lo;}
    }
    public static class Object
    {
        public static T Instantiate<T>(T source) where T:class
        {
            var mesh=source as Mesh;if(mesh==null)throw new NotSupportedException("Only Mesh cloning belongs to this harness");return mesh.Copy() as T;
        }
    }
    public class Mesh
    {
        public string name;public Rendering.IndexFormat indexFormat;public Bounds bounds;
        Vector3[] vertexData=new Vector3[0],normalData=new Vector3[0];Vector2[] uvData=new Vector2[0];Vector4[] tangentData=new Vector4[0];
        public Vector3[] vertices {get{return (Vector3[])vertexData.Clone();}set{vertexData=value==null?new Vector3[0]:(Vector3[])value.Clone();}}
        public Vector3[] normals {get{return (Vector3[])normalData.Clone();}set{normalData=value==null?new Vector3[0]:(Vector3[])value.Clone();}}
        public Vector4[] tangents {get{return (Vector4[])tangentData.Clone();}set{tangentData=value==null?new Vector4[0]:(Vector4[])value.Clone();}}
        public Vector2[] uv {get{return (Vector2[])uvData.Clone();}set{uvData=value==null?new Vector2[0]:(Vector2[])value.Clone();}}
        readonly List<int[]> submeshes=new List<int[]>{new int[0]};
        public int subMeshCount {get{return submeshes.Count;}set{while(submeshes.Count<value)submeshes.Add(new int[0]);while(submeshes.Count>value)submeshes.RemoveAt(submeshes.Count-1);}}
        public int[] triangles {get{return submeshes.SelectMany(x=>x).ToArray();}set{submeshes.Clear();submeshes.Add(value);}}
        public int[] GetTriangles(int i){return (int[])submeshes[i].Clone();}public void SetTriangles(int[] indices,int i){submeshes[i]=(int[])indices.Clone();}
        public Mesh Copy(){var m=new Mesh{name=name,indexFormat=indexFormat,vertices=vertices==null?null:(Vector3[])vertices.Clone(),uv=uv==null?null:(Vector2[])uv.Clone(),normals=(Vector3[])normals.Clone(),tangents=(Vector4[])tangents.Clone(),bounds=bounds};m.subMeshCount=subMeshCount;for(int i=0;i<subMeshCount;i++)m.SetTriangles(GetTriangles(i),i);return m;}
        public void RecalculateNormals(){}public void RecalculateBounds(){if(vertices==null||vertices.Length==0)return;bounds=new Bounds(vertices[0],Vector3.zero);foreach(var v in vertices)bounds.Encapsulate(v);}
        public int vertexCount {get{return vertices==null?0:vertices.Length;}}
    }
    public sealed class MeshFilter : Component { public Mesh sharedMesh; }
    public class Collider : Component { public bool isTrigger;public bool enabled=true; }
    public sealed class BoxCollider : Collider { public Vector3 center,size; }
    public sealed class MeshCollider : Collider { public Mesh sharedMesh; public bool convex; }
    public class Renderer : Component { public Material sharedMaterial;private Material[] materials;public Material[] sharedMaterials {get{return materials??(sharedMaterial==null?new Material[0]:new[]{sharedMaterial});}set{materials=value;sharedMaterial=value.Length>0?value[0]:null;}} public bool enabled=true;public Rendering.ShadowCastingMode shadowCastingMode;public bool receiveShadows; }
    public sealed class MeshRenderer : Renderer { }
    public sealed class SkinnedMeshRenderer : Renderer { }
    public sealed class Shader { public string name; public static readonly HashSet<string> Missing=new HashSet<string>(); public static Shader Find(string name){return Missing.Contains(name)?null:new Shader{name=name};} }
    public class Texture { }
    public sealed class Material { public string name;public Shader shader;public Color color;public Texture mainTexture;public int renderQueue;public Material(Shader s){shader=s;} }
    public static class Time { public static int frameCount; public static float realtimeSinceStartup; }
    public static class Debug { public static int errorCount;public static readonly List<string> logs=new List<string>();public static void Log(object s){logs.Add(Convert.ToString(s));}public static void LogWarning(object s){logs.Add(Convert.ToString(s));}public static void LogError(object s){errorCount++;logs.Add(Convert.ToString(s));} }
}
namespace UnityEngine.Rendering { public enum ShadowCastingMode { Off,On,TwoSided } public enum IndexFormat {UInt16,UInt32} }
public sealed class GameDatabase
{
    public static GameDatabase Instance=new GameDatabase();public bool missingTexture;
    public readonly Dictionary<string,UnityEngine.GameObject> modelPrefabs=new Dictionary<string,UnityEngine.GameObject>();
    public UnityEngine.Texture GetTexture(string path,bool normal){return missingTexture?null:new UnityEngine.Texture();}
    public UnityEngine.GameObject GetModelPrefab(string path){UnityEngine.GameObject value;return modelPrefabs.TryGetValue(path,out value)?value:null;}
}
public sealed class CameraManager { public enum CameraMode { IVA,Flight } public static CameraManager Instance=new CameraManager();public CameraMode currentCameraMode=CameraMode.IVA; }
public static class HighLogic { public static bool LoadedSceneIsFlight=true; }
public class Vessel { }
public class PartModule : UnityEngine.MonoBehaviour { public Part part; }
public sealed class AttachNode { public string id;public Part attachedPart; }
public class Part : UnityEngine.MonoBehaviour
{
    public Vessel vessel;public List<PartModule> Modules=new List<PartModule>();public readonly List<AttachNode> attachNodes=new List<AttachNode>();
    public AttachNode FindAttachNode(string id){return attachNodes.FirstOrDefault(n=>n.id==id);}
    public AttachNode FindAttachNodeByPart(Part p){return attachNodes.FirstOrDefault(n=>n.attachedPart==p);}
}
public sealed class ModuleDockingNode : PartModule { public string nodeTransformName,state;public ModuleDockingNode otherNode; }
public sealed class InternalModel : UnityEngine.MonoBehaviour { public string internalName="test"; }
public sealed class InternalProp : UnityEngine.MonoBehaviour { public bool hasModel;public InternalModel internalModel; }
public class InternalModule : UnityEngine.MonoBehaviour { public InternalModel internalModel;public InternalProp internalProp;public Part part;public Vessel vessel { get { return part.vessel; } }public virtual void OnLoad(ConfigNode n){}public virtual void OnAwake(){} }

namespace FreeIva
{
    public sealed class CutParameter
    {
        public enum Type {Mesh,Cube,ProceduralCylinder}public Type type;public string target,toolName;
        public static CutParameter LoadFromCfg(ConfigNode n){return new CutParameter{type=(Type)Enum.Parse(typeof(Type),n.GetValue("type")),target=n.GetValue("target"),toolName=n.GetValue("tool")};}
    }
    public static class MeshCutter
    {
        public static void CreateToolsForCutParameters(InternalModel model,List<CutParameter> cuts){throw new InvalidOperationException("Native mesh cutting is outside this dependency-double harness");}
        public static void CutInternalModel(InternalModel model,List<CutParameter> cuts){throw new InvalidOperationException("Native mesh cutting is outside this dependency-double harness");}
        public static void DestroyTools(ref List<CutParameter> cuts){}
    }
    public static class ColliderUtil
    {
        public static UnityEngine.Collider CreateCollider(UnityEngine.Transform transform,ConfigNode node,string context)
        {
            if(node.GetValue("shape")!="Box"){UnityEngine.Debug.LogError("unsupported dependency-double collider shape");return null;}
            var collider=transform.gameObject.AddComponent<UnityEngine.BoxCollider>();var center=UnityEngine.Vector3.zero;var size=UnityEngine.Vector3.zero;node.TryGetValue("center",ref center);node.TryGetValue("dimensions",ref size);collider.center=center;collider.size=size;return collider;
        }
    }
    public sealed class InternalModuleFreeIva : InternalModule
    {
        static readonly Dictionary<InternalModel,InternalModuleFreeIva> registry=new Dictionary<InternalModel,InternalModuleFreeIva>();
        public readonly List<FreeIvaHatch> Hatches=new List<FreeIvaHatch>();
        public static InternalModuleFreeIva GetForModel(InternalModel model){InternalModuleFreeIva m;return model!=null&&registry.TryGetValue(model,out m)?m:null;}
        public static InternalModuleFreeIva Register(InternalModel model){var previous=GetForModel(model);if(previous!=null)return previous;var m=new InternalModuleFreeIva();m.internalModel=model;registry[model]=m;return m;}
        public static void Unregister(InternalModel model){registry.Remove(model);}
    }
    public sealed class HatchConfig : UnityEngine.MonoBehaviour { }
    public sealed class ModuleFreeIva : PartModule { public string passThroughNodeA,passThroughNodeB;public bool allowsUnbuckling=true; }
    public class FreeIvaHatch : InternalModule
    {
        public string attachNodeId="",airlockName="",dockingPortNodeName="",doorTransformName="",tubeTransformName="";
        public bool requireDeploy,hideDoorWhenConnected,CanEVA,blockedByAnimation;
        public float tubeExtent;public UnityEngine.Vector3 inwardsDirection=UnityEngine.Vector3.up;
        public bool IsOpen {get;private set;}public bool DesiredOpen {get;private set;}
        public FreeIvaHatch ConnectedHatch {get;set;}public UnityEngine.Transform[] HandleTransforms {get;private set;}
        public int baseAwakeCalls,baseLoadCalls,evaCalls; public bool? NamedTubeConvexAtBaseLoad; public bool DoNotReparentNativeDoor,FailNativeAwakeAfterOpen; UnityEngine.Transform door;
        public override void OnLoad(ConfigNode n)
        {
            baseLoadCalls++;
            if(!String.IsNullOrEmpty(tubeTransformName))
            {
                var model=internalModel??internalProp.internalModel;
                var tube=model.GetComponentsInChildren<UnityEngine.Transform>(true).FirstOrDefault(t=>t.name==tubeTransformName);
                if(tube!=null)NamedTubeConvexAtBaseLoad=tube.GetComponentsInChildren<UnityEngine.MeshCollider>(true).Any(c=>c.convex);
            }
            if(n.HasValue("position")){var a=n.GetValue("position").Split(',').Select(s=>Single.Parse(s,CultureInfo.InvariantCulture)).ToArray();transform.localPosition=new UnityEngine.Vector3(a[0],a[1],a[2]);}
            if(n.HasValue("rotation")){var a=n.GetValue("rotation").Split(',').Select(s=>Single.Parse(s,CultureInfo.InvariantCulture)).ToArray();transform.localRotation=new UnityEngine.Quaternion(a[0],a[1],a[2],a[3]);}
            var all=(internalProp.hasModel ? internalProp.GetComponentsInChildren<UnityEngine.Transform>(true) : internalModel.GetComponentsInChildren<UnityEngine.Transform>(true));
            HandleTransforms=n.GetValues("handleTransformName").Select(name=>all.FirstOrDefault(t=>t.name==name)).Where(t=>t!=null).ToArray();
            door=all.FirstOrDefault(t=>t.name==doorTransformName);
            if(door!=null){door.gameObject.layer=16;
                foreach(var colliderNode in n.GetNodes("DoorCollider")){var collider=door.gameObject.AddComponent<UnityEngine.BoxCollider>();collider.center=ParseVector(colliderNode.GetValue("center"));collider.size=ParseVector(colliderNode.GetValue("dimensions"));}
                if(!internalProp.hasModel && !DoNotReparentNativeDoor)door.SetParent(transform,true);}
            if(HandleTransforms.Length>0)foreach(var colliderNode in n.GetNodes("HandleCollider")){var collider=HandleTransforms[0].gameObject.AddComponent<UnityEngine.BoxCollider>();collider.center=ParseVector(colliderNode.GetValue("center"));collider.size=ParseVector(colliderNode.GetValue("dimensions"));}
        }
        static UnityEngine.Vector3 ParseVector(string text){if(text==null)return UnityEngine.Vector3.zero;var a=text.Split(',').Select(s=>Single.Parse(s,CultureInfo.InvariantCulture)).ToArray();return new UnityEngine.Vector3(a[0],a[1],a[2]);}
        public override void OnAwake(){if(HighLogic.LoadedSceneIsFlight&&(part==null||internalModel==null||internalProp==null))throw new InvalidOperationException("native Awake requires part/internal/prop context");baseAwakeCalls++;var native=InternalModuleFreeIva.GetForModel(internalModel);if(native!=null)native.Hatches.Add(this);if(FailNativeAwakeAfterOpen){IsOpen=DesiredOpen=true;if(door!=null)door.gameObject.SetActive(false);throw new InvalidOperationException("simulated native Awake failure after door state changed");}}
        public bool IsBlockedByAnimation(bool checkConnectedHatch=true){return blockedByAnimation || (checkConnectedHatch && ConnectedHatch!=null && ConnectedHatch.blockedByAnimation);}
        public void SetOpened(bool open,bool allowSounds=true){Open(open,allowSounds);}
        protected virtual void Open(bool open,bool allowSounds=true)
        {
            // Only native state semantics needed by the custom class. Connection
            // discovery/deploy adapters/EVA obstruction/coroutines are NOT run.
            if(IsBlockedByAnimation() || (ConnectedHatch==null && !CanEVA && (attachNodeId!="" || dockingPortNodeName!="")))open=false;
            if(open && CanEVA){evaCalls++;return;}
            if(door!=null)door.gameObject.SetActive(!open);
            IsOpen=DesiredOpen=open;
            if(ConnectedHatch!=null && ConnectedHatch.IsOpen!=open)ConnectedHatch.SetOpened(open,allowSounds);
        }
    }
}
