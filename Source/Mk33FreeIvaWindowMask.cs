// SPDX-License-Identifier: GPL-2.0-or-later
// Window-only depth prepass. It uses installed glass geometry but never changes
// the glass mesh/material, creates a collider, or masks a hatch opening.
using System;
using UnityEngine;
using UnityEngine.Rendering;
using FreeIva;

public sealed class Mk33FreeIvaWindowMask : InternalModule
{
    private const string MaskName = "Mk33WindowDepthMask";
    // FreeIVA promotes the occupied IVA's opaque renderers to queue 999. A
    // window-only mask must precede those too: a depth pass cannot erase colour
    // already drawn behind the window. Do not change native hull-mask queues.
    private const int WindowDepthQueue = InternalModuleFreeIva.CURRENT_PART_RENDER_QUEUE - 1;
    private Material ownedMaterial;
    private MeshRenderer depthRenderer;
    private Transform maskTransform;
    private bool shaderWarningShown;
    private bool bindingWarningShown;

    private InternalModel Model
    {
        get { return internalModel ?? (internalProp == null ? null : internalProp.internalModel); }
    }

    public override void OnLoad(ConfigNode node)
    {
        base.OnLoad(node);
        InternalModel model = Model;
        if (model == null)
        {
            Debug.LogError("[Mk33FreeIVA] Mk33FreeIvaWindowMask must be placed in INTERNAL.");
            return;
        }

        // Prefab clones and repeated OnLoad must retain one complete mask.
        Transform previous = model.transform.Find(MaskName);
        if (previous != null)
        {
            Mk33WindowMaskMarker marker = previous.GetComponent<Mk33WindowMaskMarker>();
            MeshFilter previousFilter = previous.GetComponent<MeshFilter>();
            if (marker != null && marker.complete && previousFilter != null && previousFilter.sharedMesh != null)
            {
                maskTransform = previous;
                depthRenderer = previous.GetComponent<MeshRenderer>();
                return;
            }
            Debug.LogError("[Mk33FreeIVA] " + model.internalName + ": conflicting or incomplete " + MaskName + ".");
            return;
        }

        try
        {
            string sourceName = node.GetValue("sourceTransform");
            Transform source = Find(model.transform, sourceName);
            MeshFilter filter = source == null ? null : source.GetComponent<MeshFilter>();
            MeshRenderer renderer = source == null ? null : source.GetComponent<MeshRenderer>();
            if (filter == null || filter.sharedMesh == null || renderer == null)
                throw new InvalidOperationException("window source '" + sourceName + "' has no mesh/renderer");

            Mesh glass = filter.sharedMesh;
            Vector3[] vertices = glass.vertices;
            int[] original = glass.triangles;
            if (vertices.Length == 0 || original.Length == 0 || original.Length % 3 != 0)
                throw new InvalidOperationException("window source has an empty or invalid triangle array");
            for (int i = 0; i < original.Length; ++i)
                if (original[i] < 0 || original[i] >= vertices.Length)
                    throw new InvalidOperationException("window source has an invalid vertex index");

            // Bake the complete source hierarchy into INTERNAL-local coordinates.
            // Both windings are needed because native DepthMask_Culling culls
            // back faces and original glass may be authored in either direction.
            Matrix4x4 matrix = model.transform.worldToLocalMatrix * source.localToWorldMatrix;
            for (int i = 0; i < vertices.Length; ++i)
            {
                vertices[i] = matrix.MultiplyPoint3x4(vertices[i]);
                if (!Finite(vertices[i])) throw new InvalidOperationException("window source has non-finite geometry");
            }
            int[] triangles = new int[checked(original.Length * 2)];
            for (int i = 0; i < original.Length; i += 3)
            {
                triangles[i] = original[i];
                triangles[i + 1] = original[i + 1];
                triangles[i + 2] = original[i + 2];
                triangles[original.Length + i] = original[i];
                triangles[original.Length + i + 1] = original[i + 2];
                triangles[original.Length + i + 2] = original[i + 1];
            }

            Mesh mesh = new Mesh();
            mesh.name = MaskName + "_" + model.internalName;
            mesh.indexFormat = vertices.Length > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
            mesh.vertices = vertices;
            mesh.triangles = triangles;
            mesh.RecalculateBounds();

            GameObject mask = new GameObject(MaskName);
            mask.layer = (int)Layers.InternalSpace;
            mask.transform.SetParent(model.transform, false);
            mask.AddComponent<MeshFilter>().sharedMesh = mesh;
            depthRenderer = mask.AddComponent<MeshRenderer>();
            // Never assign the original colour material as a placeholder. Until
            // the native depth shader is ready, keep this extra renderer hidden.
            depthRenderer.enabled = false;
            depthRenderer.shadowCastingMode = ShadowCastingMode.Off;
            depthRenderer.receiveShadows = false;
            mask.AddComponent<Mk33WindowMaskMarker>().complete = true;
            maskTransform = mask.transform;
            Debug.Log("[Mk33FreeIVA] " + model.internalName + ": built window-only depth mask (" + original.Length / 3 + " source triangles); original glass retained.");
        }
        catch (Exception error)
        {
            Debug.LogError("[Mk33FreeIVA] " + model.internalName + ": window depth-mask construction failed: " + error.Message);
        }
    }

    private void Start() { RefreshRuntimeMask(); }
    private void LateUpdate() { RefreshRuntimeMask(); }

    private void RefreshRuntimeMask()
    {
        if (!HighLogic.LoadedSceneIsFlight) return;
        InternalModel model = Model;
        if (model == null) return;
        // Private fields do not survive prefab cloning. Resolve the serialized
        // complete marker on the live INTERNAL, including an inactive mask.
        if (maskTransform == null || depthRenderer == null)
        {
            Transform candidate = model.transform.Find(MaskName);
            Mk33WindowMaskMarker marker = candidate == null ? null : candidate.GetComponent<Mk33WindowMaskMarker>();
            if (marker == null || !marker.complete) return;
            maskTransform = candidate;
            depthRenderer = candidate.GetComponent<MeshRenderer>();
            if (depthRenderer == null) return;
        }

        InternalModuleFreeIva native = InternalModuleFreeIva.GetForModel(model);
        if (native == null) return; // Native Awake/cache may not have run yet.
        if (native.internalDepthMaskName != MaskName)
        {
            depthRenderer.enabled = false;
            if (!bindingWarningShown)
            {
                Debug.LogError("[Mk33FreeIVA] " + model.internalName + ": window mask requires internalDepthMaskName = " + MaskName + ".");
                bindingWarningShown = true;
            }
            return;
        }
        bindingWarningShown = false;
        // Repair a stale/missing prefab reference without touching the original
        // external depth mask, native shaders, or another INTERNAL's renderer.
        if (native.internalDepthMask != maskTransform) native.internalDepthMask = maskTransform;

        Shader shader = null;
        try { shader = Utils.GetDepthMaskCullingShader(); }
        catch (Exception) { /* Asset loader may not be ready; retry next frame. */ }
        if (shader == null || !shader.isSupported)
        {
            depthRenderer.enabled = false;
            if (!shaderWarningShown)
            {
                Debug.LogError("[Mk33FreeIVA] " + model.internalName + ": FreeIVA depth shader unavailable; extra window renderer disabled, retrying when ready.");
                shaderWarningShown = true;
            }
            return;
        }
        shaderWarningShown = false;
        if (ownedMaterial == null)
        {
            ownedMaterial = new Material(shader);
            ownedMaterial.name = MaskName + "_" + model.internalName;
        }
        // A private material avoids changing the singleton used by every other
        // FreeIVA IVA. It also repairs later render-queue/shader substitutions.
        if (ownedMaterial.shader != shader) ownedMaterial.shader = shader;
        if (ownedMaterial.renderQueue != WindowDepthQueue) ownedMaterial.renderQueue = WindowDepthQueue;
        if (depthRenderer.sharedMaterial != ownedMaterial) depthRenderer.sharedMaterial = ownedMaterial;
        depthRenderer.gameObject.layer = (int)Layers.InternalSpace;
        depthRenderer.shadowCastingMode = ShadowCastingMode.Off;
        depthRenderer.receiveShadows = false;
        depthRenderer.enabled = true;

        // Same mode rule as native RefreshDepthMasks. Applying it locally also
        // handles a late-created/rebound IVA after the camera-change event.
        CameraManager cameraManager = CameraManager.Instance;
        if (cameraManager != null)
        {
            bool active = cameraManager.currentCameraMode != CameraManager.CameraMode.Flight;
            if (maskTransform.gameObject.activeSelf != active) maskTransform.gameObject.SetActive(active);
        }
    }

    private void OnDestroy()
    {
        if (ownedMaterial != null) UnityEngine.Object.Destroy(ownedMaterial);
        ownedMaterial = null;
    }

    private static bool Finite(Vector3 v)
    {
        return !Single.IsNaN(v.x) && !Single.IsInfinity(v.x) &&
               !Single.IsNaN(v.y) && !Single.IsInfinity(v.y) &&
               !Single.IsNaN(v.z) && !Single.IsInfinity(v.z);
    }

    private static Transform Find(Transform root, string name)
    {
        if (String.IsNullOrEmpty(name)) return null;
        if (root.name == name) return root;
        for (int i = 0; i < root.childCount; ++i)
        {
            Transform found = Find(root.GetChild(i), name);
            if (found != null) return found;
        }
        return null;
    }
}

public sealed class Mk33WindowMaskMarker : MonoBehaviour { public bool complete; }
