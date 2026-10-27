// SPDX-License-Identifier: GPL-2.0-or-later
// Builds colliders from the user's installed Mk-33 IVA assets after FreeIVA cuts.
// No Mk-33 model, texture, or source triangle data is embedded in this assembly.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Threading;
using FreeIva;
using UnityEngine;
using UnityEngine.Rendering;

[assembly: AssemblyTitle("Mk33FreeIVA")]
[assembly: AssemblyDescription("Post-cut IVA collision geometry for Mk-33")]
[assembly: AssemblyVersion("0.3.5.0")]
[assembly: AssemblyFileVersion("0.3.5.0")]
[assembly: KSPAssembly("Mk33FreeIVA", 0, 3)]
[assembly: KSPAssemblyDependency("FreeIva", 0, 2)]

public sealed class Mk33FreeIvaGeometry : InternalModule
{
    private const int KerbalLayer = 16;
    private const string RootName = "Mk33Shell";
    [SerializeField] private bool loadAttempted;
    [NonSerialized] private bool bootStarted;
    [NonSerialized] private Part walkGatePart;

    public override void OnLoad(ConfigNode node)
    {
        loadAttempted = true;
        base.OnLoad(node);
        InternalModel model = internalModel;
        if (model == null && internalProp != null) model = internalProp.internalModel;
        if (model == null)
        {
            Debug.LogError("[Mk33FreeIVA] Mk33FreeIvaGeometry must be placed directly in INTERNAL.");
            return;
        }

        Transform existing = model.transform.Find(RootName);
        if (existing != null)
        {
            var marker = existing.GetComponent<Mk33ColliderMarker>();
            if (marker != null && marker.complete) return; // Serialized prefab or repeated OnLoad.
            Error(model, "A conflicting or incomplete '" + RootName + "' exists; refusing duplicate colliders.");
            return;
        }

        var sources = new List<MeshFilter>();
        var cuts = new List<CutParameter>();
        var names = new HashSet<string>(StringComparer.Ordinal);
        GameObject root = null;
        try
        {
            foreach (string hatchId in node.GetValues("requiredHatchId"))
            {
                int occurrence = 0;
                Transform door = Find(model.transform, "Mk33Pressure_" + hatchId + "_Door", ref occurrence);
                Mk33PressurePlateMarker seal = door == null ? null : door.GetComponent<Mk33PressurePlateMarker>();
                BoxCollider collider = door == null ? null : door.GetComponent<BoxCollider>();
                MeshRenderer renderer = door == null ? null : door.GetComponent<MeshRenderer>();
                if (seal == null || !seal.complete || collider == null || !collider.enabled || collider.isTrigger ||
                    collider.gameObject.layer != KerbalLayer || renderer == null || renderer.sharedMaterial == null)
                    throw new InvalidOperationException("Required pressure hatch '" + hatchId + "' is not complete; refusing to cut an unsealed opening.");
            }
            foreach (string shellName in node.GetValues("requiredShell"))
            {
                int occurrence = 0;
                Transform shell = Find(model.transform, shellName, ref occurrence);
                Mk33FreeIvaColliderSetup.PrepareImportedShell(shell, "Required corridor shell '" + shellName + "'");
            }
            foreach (string doorName in node.GetValues("requiredOriginalDoor"))
            {
                int occurrence = 0;
                Transform door = Find(model.transform, doorName, ref occurrence);
                Mk33OriginalHatchMarker doorMarker = door == null ? null : door.GetComponent<Mk33OriginalHatchMarker>();
                if (doorMarker == null || !doorMarker.complete || doorMarker.sealedDoor == null ||
                    doorMarker.sealedDoor.GetComponentsInChildren<Renderer>(true).Length == 0)
                    throw new InvalidOperationException("Required original pressure door '" + doorName + "' is not ready; refusing to cut its opening.");
            }
            foreach (string sourceName in node.GetValues("sourceTransform"))
            {
                if (!names.Add(sourceName)) throw new InvalidOperationException("Duplicate sourceTransform: " + sourceName);
                MeshFilter source = RequireMesh(model, sourceName);
                // Existing solid source colliders would remain uncut and become hidden blockers.
                foreach (Collider collider in source.GetComponents<Collider>())
                    if (collider.enabled && !collider.isTrigger)
                        throw new InvalidOperationException("Source '" + sourceName + "' already has a solid collider; explicit compatibility work is required.");
                sources.Add(source);
            }
            if (sources.Count == 0) throw new InvalidOperationException("No sourceTransform values were configured.");

            // FreeIVA's parser uses float.TryParse without an explicit culture. Limit the
            // invariant culture to this synchronous parser call; restore it immediately.
            CultureInfo previous = Thread.CurrentThread.CurrentCulture;
            try
            {
                Thread.CurrentThread.CurrentCulture = CultureInfo.InvariantCulture;
                foreach (ConfigNode cutNode in node.GetNodes("Cut"))
                {
                    ValidateCutNode(cutNode);
                    CutParameter cut = CutParameter.LoadFromCfg(cutNode);
                    if (cut == null) throw new InvalidOperationException("FreeIVA rejected a Cut node.");
                    RequireMesh(model, cut.target);
                    if (!names.Contains(cut.target))
                        throw new InvalidOperationException("Cut target '" + cut.target + "' is missing from sourceTransform; it would have no matching physical shell.");
                    if (cut.type == CutParameter.Type.Mesh) RequireMesh(model, cut.toolName);
                    cuts.Add(cut);
                }
            }
            finally { Thread.CurrentThread.CurrentCulture = previous; }

            if (cuts.Count != 0)
            {
                MeshCutter.CreateToolsForCutParameters(model, cuts);
                MeshCutter.CutInternalModel(model, cuts);
            }

            root = new GameObject(RootName);
            root.layer = KerbalLayer;
            root.transform.SetParent(model.transform, false);
            var marker = root.AddComponent<Mk33ColliderMarker>();
            int triangleCount = 0;
            foreach (MeshFilter source in sources)
            {
                Mesh original = source.sharedMesh;
                if (original == null || original.vertexCount == 0)
                    throw new InvalidOperationException("Source '" + source.name + "' is empty after cutting.");

                // Bake the full hierarchy into internal-local coordinates. This preserves
                // non-uniform parent scales and rotations without approximating lossyScale.
                Matrix4x4 matrix = model.transform.worldToLocalMatrix * source.transform.localToWorldMatrix;
                Vector3[] vertices = original.vertices;
                for (int i = 0; i < vertices.Length; ++i)
                {
                    vertices[i] = matrix.MultiplyPoint3x4(vertices[i]);
                    if (!Finite(vertices[i])) throw new InvalidOperationException("Non-finite vertex in '" + source.name + "'.");
                }
                int[] triangles = original.triangles;
                if (triangles.Length == 0 || triangles.Length % 3 != 0)
                    throw new InvalidOperationException("Invalid triangle array in '" + source.name + "'.");
                if (matrix.determinant < 0)
                    for (int i = 0; i < triangles.Length; i += 3)
                    {
                        int swap = triangles[i + 1]; triangles[i + 1] = triangles[i + 2]; triangles[i + 2] = swap;
                    }
                Mesh mesh = new Mesh();
                mesh.name = "Mk33FreeIVA_" + source.name;
                mesh.indexFormat = vertices.Length > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
                mesh.vertices = vertices;
                mesh.triangles = triangles;
                mesh.RecalculateBounds();

                GameObject child = new GameObject("collision_" + source.name);
                child.layer = KerbalLayer;
                child.transform.SetParent(root.transform, false);
                MeshCollider collider = child.AddComponent<MeshCollider>();
                collider.convex = false;
                collider.isTrigger = false;
                collider.sharedMesh = mesh;
                triangleCount += triangles.Length / 3;
            }
            marker.complete = true;
            marker.sourceCount = sources.Count;
            Debug.Log("[Mk33FreeIVA] " + model.internalName + ": built " + sources.Count + " post-cut collider meshes (" + triangleCount + " triangles). KSP traversal still requires an in-game test.");
        }
        catch (Exception exception)
        {
            Error(model, exception.GetType().Name + ": " + exception.Message + ". This INTERNAL is NOT validated; do not use FreeIVA here until corrected.");
            // Keep any already created colliders solid; never globally disable collision.
            // An incomplete marker prevents silently stacking another partial shell later.
        }
        finally
        {
            if (cuts.Count != 0)
            {
                // DestroyTools permits null tools (Unity Destroy(null) is harmless).
                MeshCutter.DestroyTools(ref cuts);
            }
        }
    }

    public override void OnAwake()
    {
        // Awake may run before OnLoad creates the shell. Validate after boot.
    }

    private void Start()
    {
        bootStarted = true;
        ValidateRuntimeReadiness();
    }

    private void LateUpdate()
    {
        ValidateRuntimeReadiness();
    }

    private void ValidateRuntimeReadiness()
    {
        if (!bootStarted || !HighLogic.LoadedSceneIsFlight || internalModel == null || part == null) return;
        walkGatePart = part;
        Transform shell = internalModel.transform.Find(RootName);
        Mk33ColliderMarker marker = shell == null ? null : shell.GetComponent<Mk33ColliderMarker>();
        if (marker != null && marker.complete)
            Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
        else if (loadAttempted)
            Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, true, "collision shell is incomplete in " + internalModel.internalName);
    }

    private void OnDestroy()
    {
        Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
    }

    private static MeshFilter RequireMesh(InternalModel model, string name)
    {
        if (String.IsNullOrWhiteSpace(name)) throw new InvalidOperationException("A transform name is missing.");
        int index = 0;
        string actual = name;
        int comma = name.LastIndexOf(',');
        if (comma >= 0)
        {
            if (!Int32.TryParse(name.Substring(comma + 1), NumberStyles.None, CultureInfo.InvariantCulture, out index) || index < 0)
                throw new InvalidOperationException("Invalid transform occurrence selector '" + name + "'.");
            actual = name.Substring(0, comma);
        }
        Transform found = Find(model.transform, actual, ref index);
        if (found == null) throw new InvalidOperationException("Transform '" + name + "' was not found.");
        MeshFilter filter = found.GetComponent<MeshFilter>();
        if (filter == null || filter.sharedMesh == null)
            throw new InvalidOperationException("Transform '" + name + "' has no readable MeshFilter.");
        return filter;
    }

    private static Transform Find(Transform root, string name, ref int occurrence)
    {
        if (root.name == name && occurrence-- == 0) return root;
        for (int i = 0; i < root.childCount; ++i)
        {
            Transform found = Find(root.GetChild(i), name, ref occurrence);
            if (found != null) return found;
        }
        return null;
    }

    private static void ValidateCutNode(ConfigNode node)
    {
        string kind = node.GetValue("type");
        CutParameter.Type type;
        if (!Enum.TryParse(kind, out type) || !Enum.IsDefined(typeof(CutParameter.Type), type))
            throw new InvalidOperationException("Unknown Cut type '" + kind + "'.");
        if (String.IsNullOrWhiteSpace(node.GetValue("target"))) throw new InvalidOperationException("Cut target is required.");
        if (type == CutParameter.Type.Mesh)
        {
            if (String.IsNullOrWhiteSpace(node.GetValue("tool"))) throw new InvalidOperationException("Mesh Cut tool is required.");
            return;
        }
        foreach (string field in new[] { "position", "rotation", "scale" })
        {
            if (!node.HasValue(field)) throw new InvalidOperationException("Cut " + field + " must be explicit.");
            // ConfigNode.ParseVector3 can turn malformed input into a default vector.
            // Validate each component first so an invalid position cannot cut the origin.
            string[] components = node.GetValue(field).Split(',');
            if (components.Length != 3) throw new InvalidOperationException("Cut " + field + " needs three comma-separated numbers.");
            float x, y, z;
            if (!Single.TryParse(components[0], NumberStyles.Float, CultureInfo.InvariantCulture, out x) ||
                !Single.TryParse(components[1], NumberStyles.Float, CultureInfo.InvariantCulture, out y) ||
                !Single.TryParse(components[2], NumberStyles.Float, CultureInfo.InvariantCulture, out z))
                throw new InvalidOperationException("Invalid Cut " + field + ".");
            Vector3 vector = new Vector3(x, y, z);
            if (!Finite(vector)) throw new InvalidOperationException("Invalid Cut " + field + ".");
            if (field == "scale" && (vector.x <= 0 || vector.y <= 0 || vector.z <= 0))
                throw new InvalidOperationException("Cut scale components must be positive.");
        }
        if (type == CutParameter.Type.ProceduralCylinder)
        {
            float radius, height; int slices;
            if (!Single.TryParse(node.GetValue("radius"), NumberStyles.Float, CultureInfo.InvariantCulture, out radius) || !Finite(radius) || radius <= 0 ||
                !Single.TryParse(node.GetValue("height"), NumberStyles.Float, CultureInfo.InvariantCulture, out height) || !Finite(height) || height <= 0 ||
                !Int32.TryParse(node.GetValue("slices"), NumberStyles.Integer, CultureInfo.InvariantCulture, out slices) || slices < 8 || slices > 128)
                throw new InvalidOperationException("ProceduralCylinder requires positive radius/height and 8..128 slices.");
        }
    }

    private static bool Finite(Vector3 v) { return Finite(v.x) && Finite(v.y) && Finite(v.z); }
    private static bool Finite(float f) { return !Single.IsNaN(f) && !Single.IsInfinity(f); }
    private static void Error(InternalModel model, string message) { Debug.LogError("[Mk33FreeIVA] " + model.internalName + ": " + message); }
}

// Cloned together with the INTERNAL prefab; prevents duplicate OnLoad processing.
public sealed class Mk33ColliderMarker : MonoBehaviour
{
    public bool complete;
    public int sourceCount;
    public bool authored;
}

// HatchConfig only works on a PROP. These native FreeIVA fields do not have
// KSPField attributes, so direct-INTERNAL original doors need this small adapter.
// All interaction, deployment checks, coupling, tube and EVA behavior is inherited.
public sealed class Mk33FreeIvaHatch : FreeIvaHatch
{
    [KSPField] public bool centerHandlesOnHatch;
    [KSPField] public bool autoOpenWhenDocked;
    [SerializeField] private Transform originalDoor;
    [SerializeField] private bool loadReady;
    [SerializeField] private bool loadAttempted;
    [NonSerialized] private bool flightInitialized;
    [NonSerialized] private bool bootStarted;
    [NonSerialized] private bool nativeAwakeAttempted;
    [NonSerialized] private Part walkGatePart;
    private static int wrapperSequence;

    public override void OnLoad(ConfigNode node)
    {
        if (loadReady && originalDoor != null) return;
        loadAttempted = true;
        InternalModel model = internalModel ?? (internalProp == null ? null : internalProp.internalModel);
        string requestedDoor = node.GetValue("doorTransformName") ?? "crewDoor";
        try
        {
            attachNodeId = node.GetValue("attachNodeId") ?? String.Empty;
            airlockName = node.GetValue("airlockName") ?? String.Empty;
            dockingPortNodeName = node.GetValue("dockingPortNodeName") ?? String.Empty;
            tubeTransformName = node.GetValue("tubeTransformName") ?? String.Empty;
            node.TryGetValue("inwardsDirection", ref inwardsDirection);
            node.TryGetValue("requireDeploy", ref requireDeploy);
            node.TryGetValue("tubeExtent", ref tubeExtent);
            node.TryGetValue("centerHandlesOnHatch", ref centerHandlesOnHatch);
            node.TryGetValue("autoOpenWhenDocked", ref autoOpenWhenDocked);
            hideDoorWhenConnected = false;
            if (model == null || internalProp == null)
                throw new InvalidOperationException("No INTERNAL/model-owned module wrapper is available.");

            // Native loading may search either the model or a model-owned PROP.
            // Resolve the original across the whole INTERNAL first. Apply the
            // configured module pose BEFORE reparenting, so art is not moved
            // twice when native OnLoad applies that same pose later.
            Vector3 position = Vector3.zero;
            Quaternion rotation = Quaternion.identity;
            node.TryGetValue("position", ref position);
            node.TryGetValue("rotation", ref rotation);
            transform.localPosition = position;
            transform.localRotation = rotation;
            Transform art = FindOriginal(model.transform, requestedDoor);
            if (node.HasValue("extractSourceTransform"))
            {
                if (art == null) art = ExtractOriginalDoor(model, node, requestedDoor);
                Mk33ExtractedDoorMarker extracted = art.GetComponent<Mk33ExtractedDoorMarker>();
                if (extracted == null || !extracted.complete)
                    throw new InvalidOperationException("The extracted original pressure door is incomplete.");
            }
            string prefix = "Mk33OriginalPressure_" + System.Threading.Interlocked.Increment(ref wrapperSequence);
            GameObject proxy = new GameObject(prefix + "_Door");
            proxy.layer = 16;
            originalDoor = proxy.transform;
            originalDoor.SetParent(transform, false);

            // A unique proxy is visible in both native lookup scopes. Native
            // controls this proxy, including every original/skinned child,
            // instead of depending on native's conditional reparenting branch.
            bool hasArt = art != null && art.GetComponentsInChildren<Renderer>(true).Length != 0;
            Transform markerTarget;
            if (hasArt)
            {
                art.SetParent(originalDoor, true);
                art.gameObject.layer = 16;
                foreach (ConfigNode colliderNode in node.GetNodes("DoorCollider"))
                    ColliderUtil.CreateCollider(art, colliderNode, model.internalName);
                bool solid = false;
                foreach (Collider collider in art.GetComponentsInChildren<Collider>(true))
                    if (!collider.isTrigger && collider.enabled && collider.gameObject.layer == 16) solid = true;
                if (!solid)
                    throw new InvalidOperationException("Original art was found but its configured physical seal could not be built.");
                markerTarget = art;
            }
            else
            {
                // Some IVA replacements omit original door art. Replace just
                // that unavailable pressure plate with a visible solid door at
                // the configured pose; keep the alias used by the cut gate.
                if (art == null)
                {
                    GameObject alias = new GameObject(SelectorName(requestedDoor));
                    art = alias.transform;
                    art.SetParent(originalDoor, false);
                }
                else art.SetParent(originalDoor, true);
                markerTarget = art;
                CreateFallbackDoor(originalDoor, prefix + "_ReplacementPlate", inwardsDirection);
                Debug.LogWarning("[Mk33FreeIVA] " + model.internalName + ": original door '" + requestedDoor + "' has no renderer; installed a visible rectangular pressure door.");
            }

            GameObject handle = new GameObject(prefix + "_Handle");
            handle.layer = 20;
            handle.transform.SetParent(transform, false);
            BoxCollider handleCollider = handle.AddComponent<BoxCollider>();
            handleCollider.isTrigger = false;
            handleCollider.size = new Vector3(0.42f, 0.42f, 0.12f);
            ConfigNode handleNode = node.GetNode("HandleCollider");
            Vector3 dimensions = handleCollider.size;
            if (handleNode != null) handleNode.TryGetValue("dimensions", ref dimensions);
            handleCollider.size = dimensions;

            ConfigNode nativeConfig = node.CreateCopy();
            nativeConfig.RemoveValues("handleTransformName");
            nativeConfig.AddValue("handleTransformName", handle.name);
            nativeConfig.RemoveNodes("DoorCollider");
            nativeConfig.RemoveNodes("HandleCollider");
            nativeConfig.RemoveValues("doorTransformName");
            nativeConfig.AddValue("doorTransformName", proxy.name);
            doorTransformName = proxy.name;
            Mk33FreeIvaColliderSetup.PrepareNamedTube(model, tubeTransformName);
            base.OnLoad(nativeConfig);
            if (GetComponent<HatchConfig>() == null) gameObject.AddComponent<HatchConfig>();
            if (HandleTransforms == null || HandleTransforms.Length == 0)
                throw new InvalidOperationException("Native loading did not bind the generated persistent handle.");

            Mk33OriginalHatchMarker marker = markerTarget.GetComponent<Mk33OriginalHatchMarker>();
            if (marker == null) marker = markerTarget.gameObject.AddComponent<Mk33OriginalHatchMarker>();
            marker.sealedDoor = originalDoor;
            marker.complete = true;
            loadReady = true;
            ApplyOriginalDoorState();
            Debug.Log("[Mk33FreeIVA] " + model.internalName + ": bound original hatch '" + requestedDoor + "'; art=" + hasArt + "; wrapperHasModel=" + internalProp.hasModel + "; handles=" + HandleTransforms.Length + ".");
        }
        catch (Exception exception)
        {
            loadReady = false;
            if (originalDoor != null)
            {
                originalDoor.gameObject.SetActive(true);
                foreach (Mk33OriginalHatchMarker marker in originalDoor.GetComponentsInChildren<Mk33OriginalHatchMarker>(true)) marker.complete = false;
            }
            Debug.LogError("[Mk33FreeIVA] Original hatch LOAD FAILED; door='" + requestedDoor + "'; internal='" + (model == null ? "<missing>" : model.internalName) + "'; wrapperHasModel=" + (internalProp != null && internalProp.hasModel) + "; " + exception.GetType().Name + ": " + exception.Message + ". Source cuts remain blocked; loading continues.");
        }
    }

    // The Krew AIRLOCK door and its handle are four disconnected components
    // embedded in cabinMesh, while crewDoor is the separate roof EVA hatch.
    // Detach only complete triangles inside an explicit internal-local box.
    // Work on private mesh copies: never alter the installed shared Mk-33 art.
    private Transform ExtractOriginalDoor(InternalModel model, ConfigNode node, string requestedDoor)
    {
        Vector3 lower = Vector3.zero, upper = Vector3.zero;
        int expected;
        if (!node.TryGetValue("extractBoundsMin", ref lower) || !node.TryGetValue("extractBoundsMax", ref upper) ||
            !FiniteDoorVector(lower) || !FiniteDoorVector(upper) || lower.x >= upper.x || lower.y >= upper.y || lower.z >= upper.z ||
            !Int32.TryParse(node.GetValue("extractExpectedTriangles"), NumberStyles.None, CultureInfo.InvariantCulture, out expected) || expected <= 0)
            throw new InvalidOperationException("Original door extraction requires finite bounds and a positive expected triangle count.");
        Transform source = FindOriginal(model.transform, node.GetValue("extractSourceTransform"));
        MeshFilter filter = source == null ? null : source.GetComponent<MeshFilter>();
        MeshRenderer renderer = source == null ? null : source.GetComponent<MeshRenderer>();
        Mesh original = filter == null ? null : filter.sharedMesh;
        if (original == null || renderer == null || renderer.sharedMaterials.Length == 0 || original.subMeshCount == 0)
            throw new InvalidOperationException("Original pressure door source has no readable mesh/materials.");
        foreach (Collider collider in source.GetComponents<Collider>())
            if (collider.enabled && !collider.isTrigger)
                throw new InvalidOperationException("Original pressure door source already has an uncut solid collider.");
        Vector3[] vertices = original.vertices;
        Matrix4x4 sourceToInternal = model.transform.worldToLocalMatrix * source.localToWorldMatrix;
        bool[] inside = new bool[vertices.Length];
        for (int i = 0; i < vertices.Length; ++i)
        {
            Vector3 value = sourceToInternal.MultiplyPoint3x4(vertices[i]);
            if (!FiniteDoorVector(value)) throw new InvalidOperationException("Original door source has a non-finite vertex.");
            inside[i] = value.x >= lower.x && value.x <= upper.x && value.y >= lower.y && value.y <= upper.y && value.z >= lower.z && value.z <= upper.z;
        }
        var selected = new List<int[]>();
        var retained = new List<int[]>();
        int count = 0, remainingCount = 0;
        for (int submesh = 0; submesh < original.subMeshCount; ++submesh)
        {
            int[] triangles = original.GetTriangles(submesh);
            if (triangles.Length % 3 != 0) throw new InvalidOperationException("Original door source has an invalid triangle array.");
            var doorTriangles = new List<int>();
            var fixedTriangles = new List<int>();
            for (int i = 0; i < triangles.Length; i += 3)
            {
                int a = triangles[i], b = triangles[i + 1], c = triangles[i + 2];
                if (a < 0 || b < 0 || c < 0 || a >= vertices.Length || b >= vertices.Length || c >= vertices.Length)
                    throw new InvalidOperationException("Original door source has an out-of-range triangle index.");
                List<int> destination = inside[a] && inside[b] && inside[c] ? doorTriangles : fixedTriangles;
                destination.Add(a); destination.Add(b); destination.Add(c);
            }
            count += doorTriangles.Count / 3; remainingCount += fixedTriangles.Count / 3;
            selected.Add(doorTriangles.ToArray()); retained.Add(fixedTriangles.ToArray());
        }
        if (count != expected || remainingCount == 0)
            throw new InvalidOperationException("Original pressure door extraction found " + count + " triangles, expected " + expected + "; source art remains unchanged.");

        GameObject door = new GameObject(SelectorName(requestedDoor));
        door.layer = 16;
        door.transform.SetParent(model.transform, false);
        door.transform.localPosition = transform.localPosition;
        door.transform.localRotation = transform.localRotation;
        Matrix4x4 toDoor = door.transform.worldToLocalMatrix * source.localToWorldMatrix;
        Matrix4x4 normalMatrix = toDoor.inverse.transpose;
        Mesh fixedMesh = UnityEngine.Object.Instantiate(original);
        fixedMesh.name = original.name + "_WithoutMk33CentralDoor";
        Mesh doorMesh = UnityEngine.Object.Instantiate(original);
        doorMesh.name = "Mk33KrewCentralDoor_InstalledOriginalArt";
        Vector3[] normals = doorMesh.normals;
        Vector4[] tangents = doorMesh.tangents;
        for (int i = 0; i < vertices.Length; ++i) vertices[i] = toDoor.MultiplyPoint3x4(vertices[i]);
        for (int i = 0; i < normals.Length; ++i) normals[i] = normalMatrix.MultiplyVector(normals[i]).normalized;
        for (int i = 0; i < tangents.Length; ++i)
        {
            Vector3 tangent = toDoor.MultiplyVector(new Vector3(tangents[i].x, tangents[i].y, tangents[i].z)).normalized;
            tangents[i] = new Vector4(tangent.x, tangent.y, tangent.z, tangents[i].w * (toDoor.determinant < 0 ? -1 : 1));
        }
        doorMesh.vertices = vertices;
        doorMesh.normals = normals;
        doorMesh.tangents = tangents;
        bool haveBounds = false;
        Bounds bounds = new Bounds();
        for (int submesh = 0; submesh < original.subMeshCount; ++submesh)
        {
            int[] triangles = selected[submesh];
            if (toDoor.determinant < 0)
                for (int i = 0; i < triangles.Length; i += 3) { int swap = triangles[i + 1]; triangles[i + 1] = triangles[i + 2]; triangles[i + 2] = swap; }
            doorMesh.SetTriangles(triangles, submesh);
            fixedMesh.SetTriangles(retained[submesh], submesh);
            foreach (int index in triangles)
            {
                if (!haveBounds) { bounds = new Bounds(vertices[index], Vector3.zero); haveBounds = true; }
                else bounds.Encapsulate(vertices[index]);
            }
        }
        // Cloning preserves every UV/color channel. Unreferenced source vertices
        // remain in the copy, so set bounds from selected door triangles only.
        doorMesh.bounds = bounds;
        fixedMesh.RecalculateBounds();
        door.AddComponent<MeshFilter>().sharedMesh = doorMesh;
        MeshRenderer doorRenderer = door.AddComponent<MeshRenderer>();
        doorRenderer.sharedMaterials = renderer.sharedMaterials;
        doorRenderer.shadowCastingMode = renderer.shadowCastingMode;
        doorRenderer.receiveShadows = renderer.receiveShadows;
        // Commit only after selection, signature, copied art and renderer succeed.
        filter.sharedMesh = fixedMesh;
        Mk33ExtractedDoorMarker marker = door.AddComponent<Mk33ExtractedDoorMarker>();
        marker.complete = true;
        marker.triangleCount = count;
        Debug.Log("[Mk33FreeIVA] " + model.internalName + ": detached " + count + " original central AIRLOCK door/handle triangles; roof EVA door unchanged.");
        return door.transform;
    }

    private static bool FiniteDoorVector(Vector3 value)
    {
        return !Single.IsNaN(value.x) && !Single.IsNaN(value.y) && !Single.IsNaN(value.z) &&
            !Single.IsInfinity(value.x) && !Single.IsInfinity(value.y) && !Single.IsInfinity(value.z);
    }

    private static string SelectorName(string selector)
    {
        int comma = selector.LastIndexOf(',');
        return comma < 0 ? selector : selector.Substring(0, comma);
    }

    private static Transform FindOriginal(Transform root, string selector)
    {
        int occurrence = 0;
        int comma = selector.LastIndexOf(',');
        if (comma >= 0 && (!Int32.TryParse(selector.Substring(comma + 1), out occurrence) || occurrence < 0)) return null;
        return FindNth(root, SelectorName(selector), ref occurrence);
    }

    private static Transform FindNth(Transform root, string name, ref int occurrence)
    {
        if (root.name == name && occurrence-- == 0) return root;
        for (int i = 0; i < root.childCount; ++i)
        {
            Transform found = FindNth(root.GetChild(i), name, ref occurrence);
            if (found != null) return found;
        }
        return null;
    }

    private static Transform CreateFallbackDoor(Transform parent, string name, Vector3 inwards)
    {
        GameObject door = new GameObject(name);
        door.layer = 16;
        door.transform.SetParent(parent, false);
        Vector3 normal = inwards.sqrMagnitude > 0.001f ? inwards.normalized : Vector3.forward;
        Vector3 up = Mathf.Abs(Vector3.Dot(normal, Vector3.up)) > 0.9f ? Vector3.forward : Vector3.up;
        door.transform.localRotation = Quaternion.LookRotation(normal, up);
        Vector3 size = new Vector3(0.72f, 0.80f, 0.07f);
        Vector3[] vertices = new Vector3[8];
        for (int i = 0; i < 8; ++i)
            vertices[i] = new Vector3((i & 4) == 0 ? -size.x / 2 : size.x / 2, (i & 2) == 0 ? -size.y / 2 : size.y / 2, (i & 1) == 0 ? -size.z / 2 : size.z / 2);
        Mesh mesh = new Mesh();
        mesh.name = "Mk33OriginalFallbackPressureDoor";
        mesh.vertices = vertices;
        mesh.triangles = new[] { 0,1,3, 0,3,2, 4,6,7, 4,7,5, 0,4,5, 0,5,1, 2,3,7, 2,7,6, 0,2,6, 0,6,4, 1,5,7, 1,7,3 };
        Vector2[] uv = new Vector2[vertices.Length];
        for (int i = 0; i < vertices.Length; ++i) uv[i] = new Vector2(0.5f + vertices[i].x / size.x, 0.5f + vertices[i].y / size.y);
        mesh.uv = uv;
        mesh.RecalculateNormals(); mesh.RecalculateBounds();
        door.AddComponent<MeshFilter>().sharedMesh = mesh;
        MeshRenderer renderer = door.AddComponent<MeshRenderer>();
        Shader shader = Shader.Find("KSP/Diffuse") ?? Shader.Find("KSP/Unlit") ?? Shader.Find("Unlit/Color") ?? Shader.Find("Standard");
        if (shader == null) throw new InvalidOperationException("No opaque shader is available for the replacement pressure door.");
        Material material = new Material(shader);
        material.name = "Mk33OriginalFallbackMetal";
        material.color = new Color(0.82f, 0.85f, 0.87f, 1);
        if (GameDatabase.Instance != null) material.mainTexture = GameDatabase.Instance.GetTexture("Mk33FreeIVA/Models/hatchGrey", false);
        material.renderQueue = 2000;
        renderer.sharedMaterial = material;
        BoxCollider seal = door.AddComponent<BoxCollider>();
        seal.isTrigger = false; seal.center = Vector3.zero; seal.size = size;
        return door.transform;
    }

    public override void OnAwake()
    {
        TryInitializeRuntime();
    }

    private void Start()
    {
        bootStarted = true;
        TryInitializeRuntime();
    }

    private void TryInitializeRuntime()
    {
        if (!HighLogic.LoadedSceneIsFlight || flightInitialized) return;
        if (!bootStarted) { ApplyOriginalDoorState(true); return; }
        if (part != null) walkGatePart = part;
        if (!loadReady)
        {
            ApplyOriginalDoorState(true);
            if (bootStarted && loadAttempted) DisableWalking("original hatch did not finish loading");
            return;
        }
        if (nativeAwakeAttempted)
        {
            DisableWalking("native hatch initialization failed for this instance");
            return;
        }
        if (internalProp == null || internalModel == null || part == null || vessel == null ||
            InternalModuleFreeIva.GetForModel(internalModel) == null)
        {
            ApplyOriginalDoorState(true);
            return;
        }
        nativeAwakeAttempted = true;
        try { base.OnAwake(); }
        catch (Exception exception) { DisableWalking("native hatch initialization failed: " + exception.Message); return; }
        flightInitialized = true;
        SetOpened(false, false);
        ApplyOriginalDoorState();
        Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
        Debug.Log("[Mk33FreeIVA] Original hatch in " + internalModel.internalName + " initialized CLOSED; door=" + (originalDoor != null) + "; dock=" + dockingPortNodeName + ".");
    }

    private void DisableWalking(string reason)
    {
        if (HighLogic.LoadedSceneIsFlight)
        {
            if (part != null) walkGatePart = part;
            Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, true, "original hatch: " + reason);
        }
        ApplyOriginalDoorState(true);
    }

    private void OnDestroy()
    {
        Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
    }

    protected override void Open(bool open, bool allowSounds = true)
    {
        if (!loadReady || (HighLogic.LoadedSceneIsFlight && !flightInitialized)) { ApplyOriginalDoorState(true); return; }
        if (open && (!Mk33FreeIvaConnection.HasCompleteShell(this) || (!String.IsNullOrEmpty(dockingPortNodeName) && !Mk33FreeIvaConnection.IsPhysical(this)))) open = false;
        base.Open(open, allowSounds);
        ApplyOriginalDoorState();
    }

    private void LateUpdate()
    {
        if (!HighLogic.LoadedSceneIsFlight) return;
        if (!flightInitialized) { TryInitializeRuntime(); if (!flightInitialized) return; }
        if (autoOpenWhenDocked)
        {
            bool open = !String.IsNullOrEmpty(dockingPortNodeName) && Mk33FreeIvaConnection.HasCompleteShell(this) &&
                Mk33FreeIvaConnection.IsPhysical(this) && !IsBlockedByAnimation();
            if (IsOpen != open) SetOpened(open, false);
        }
        else if (IsOpen && (!Mk33FreeIvaConnection.HasCompleteShell(this) || (!String.IsNullOrEmpty(dockingPortNodeName) && (IsBlockedByAnimation() || !Mk33FreeIvaConnection.IsPhysical(this))))) SetOpened(false, false);
        ApplyOriginalDoorState();
    }

    private void ApplyOriginalDoorState(bool forceClosed = false)
    {
        if (originalDoor == null) return;
        bool open = !forceClosed && IsOpen;
        originalDoor.gameObject.SetActive(!open);
        foreach (Collider collider in originalDoor.GetComponentsInChildren<Collider>(true))
            if (collider.gameObject.layer == 16) collider.enabled = !open;
        if (!open && CameraManager.Instance != null && CameraManager.Instance.currentCameraMode == CameraManager.CameraMode.IVA)
            foreach (Renderer renderer in originalDoor.GetComponentsInChildren<Renderer>(true)) renderer.enabled = true;
    }
}

public sealed class Mk33OriginalHatchMarker : MonoBehaviour
{
    public bool complete;
    public Transform sealedDoor;
}

// Serialized with the INTERNAL prefab, independent of native hatch Awake order.
public sealed class Mk33ExtractedDoorMarker : MonoBehaviour
{
    public bool complete;
    public int triangleCount;
}
