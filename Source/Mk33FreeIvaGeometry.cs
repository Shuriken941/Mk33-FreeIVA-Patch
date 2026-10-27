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
[assembly: AssemblyVersion("0.1.0.0")]
[assembly: AssemblyFileVersion("0.1.0.0")]
[assembly: KSPAssembly("Mk33FreeIVA", 0, 1)]
[assembly: KSPAssemblyDependency("FreeIva", 0, 2)]

public sealed class Mk33FreeIvaGeometry : InternalModule
{
    private const int KerbalLayer = 16;
    private const string RootName = "Mk33Shell";

    public override void OnLoad(ConfigNode node)
    {
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
}

// HatchConfig only works on a PROP. These native FreeIVA fields do not have
// KSPField attributes, so direct-INTERNAL original doors need this small adapter.
// All interaction, deployment checks, coupling, tube and EVA behavior is inherited.
public sealed class Mk33FreeIvaHatch : FreeIvaHatch
{
    public override void OnLoad(ConfigNode node)
    {
        if (attachNodeId == null) attachNodeId = String.Empty;
        if (node.HasValue("dockingPortNodeName")) dockingPortNodeName = node.GetValue("dockingPortNodeName");
        node.TryGetValue("requireDeploy", ref requireDeploy);
        node.TryGetValue("tubeExtent", ref tubeExtent);
        node.TryGetValue("hideDoorWhenConnected", ref hideDoorWhenConnected);
        base.OnLoad(node);
    }
}
