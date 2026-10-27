// SPDX-License-Identifier: GPL-2.0-or-later
// A native FreeIVA hatch with a deterministic pressure seal and a classic
// FreeIVA Size1 door visual, read from the installed dependency at load time.
// The visible door and its primitive solid collider share the same lifetime.
using System;
using System.Collections.Generic;
using FreeIva;
using UnityEngine;
using UnityEngine.Rendering;

public sealed class Mk33FreeIvaPressureHatch : FreeIvaHatch
{
    [KSPField] public string hatchId = String.Empty;
    [KSPField] public bool requireConnected = true;
    [KSPField] public float doorRadius = 0.545f;

    [SerializeField] private Transform pressureDoor;
    [SerializeField] private MeshRenderer pressureRenderer;
    [SerializeField] private BoxCollider pressureSeal;
    [SerializeField] private Transform classicVisual;
    [SerializeField] private bool classicVisualReady;
    [SerializeField] private bool loadReady;
    [SerializeField] private bool loadAttempted;
    [NonSerialized] private bool bootStarted;
    [NonSerialized] private bool nativeAwakeAttempted;
    [NonSerialized] private Part walkGatePart;
    [NonSerialized] private bool flightInitialized;
    [NonSerialized] private bool reportedInvalidConnection;

    public override void OnLoad(ConfigNode node)
    {
        if (loadReady && pressureDoor != null) return;
        loadAttempted = true;
        try
        {
            LoadPressureHatch(node);
            loadReady = true;
        }
        catch (Exception exception)
        {
            loadReady = false;
            if (pressureDoor != null)
            {
                Mk33PressurePlateMarker marker = pressureDoor.GetComponent<Mk33PressurePlateMarker>();
                if (marker != null) marker.complete = false;
            }
            ApplyPressureState(false);
            Debug.LogError("[Mk33FreeIVA] Pressure hatch '" + hatchId + "' LOAD FAILED: " + exception.GetType().Name + ": " + exception.Message + ". Its cut remains blocked; loading continues.");
        }
    }

    private void LoadPressureHatch(ConfigNode node)
    {
        node.TryGetValue("hatchId", ref hatchId);
        node.TryGetValue("requireConnected", ref requireConnected);
        node.TryGetValue("doorRadius", ref doorRadius);
        if (String.IsNullOrEmpty(hatchId) || doorRadius < 0.50f || doorRadius > 0.65f)
            throw new InvalidOperationException("[Mk33FreeIVA] Pressure hatch needs a unique hatchId and a 0.50..0.65m doorRadius.");
        if (internalProp == null || (internalModel == null && internalProp.internalModel == null))
            throw new InvalidOperationException("[Mk33FreeIVA] Pressure hatch has no INTERNAL/module wrapper.");
        Vector3 position = Vector3.zero;
        Quaternion rotation = Quaternion.identity;
        node.TryGetValue("position", ref position);
        node.TryGetValue("rotation", ref rotation);
        transform.localPosition = position;
        transform.localRotation = rotation;

        // FreeIVA normally receives these through a separate PROP HatchConfig.
        // All settings are explicit here, including the empty local-door node.
        attachNodeId = node.GetValue("attachNodeId") ?? String.Empty;
        airlockName = node.GetValue("airlockName") ?? String.Empty;
        dockingPortNodeName = node.GetValue("dockingPortNodeName") ?? String.Empty;
        tubeTransformName = node.GetValue("tubeTransformName") ?? String.Empty;
        node.TryGetValue("requireDeploy", ref requireDeploy);
        hideDoorWhenConnected = false;
        inwardsDirection = Vector3.up;

        string prefix = "Mk33Pressure_" + hatchId;
        doorTransformName = prefix + "_Door";
        if (pressureDoor == null)
            CreatePressurePlate(prefix);

        // The base loader finds direct-INTERNAL transforms by name. Unique
        // names prevent another hatch's plate/handles from being selected.
        ConfigNode nativeConfig = node.CreateCopy();
        nativeConfig.RemoveValues("handleTransformName");
        nativeConfig.AddValue("handleTransformName", prefix + "_HandleInside");
        nativeConfig.AddValue("handleTransformName", prefix + "_HandleOutside");
        nativeConfig.RemoveValues("doorTransformName");
        nativeConfig.AddValue("doorTransformName", doorTransformName);
        Mk33FreeIvaColliderSetup.PrepareNamedTube(internalModel ?? internalProp.internalModel, tubeTransformName);
        base.OnLoad(nativeConfig);

        // Mark this direct placement as intentional. Otherwise native final
        // processing can guess an EVA/attach binding for a local corridor door.
        if (GetComponent<HatchConfig>() == null)
            gameObject.AddComponent<HatchConfig>();
        ApplyPressureState(false);
        pressureDoor.GetComponent<Mk33PressurePlateMarker>().complete = true;
    }

    private void CreatePressurePlate(string prefix)
    {
        GameObject door = new GameObject(doorTransformName);
        door.layer = 16;
        pressureDoor = door.transform;
        pressureDoor.SetParent(transform, false);

        const int sides = 32;
        const float halfThickness = 0.03f;
        Vector3[] vertices = new Vector3[sides * 2 + 2];
        for (int ring = 0; ring < 2; ++ring)
            for (int i = 0; i < sides; ++i)
            {
                float angle = i * 2.0f * Mathf.PI / sides;
                vertices[ring * sides + i] = new Vector3(doorRadius * Mathf.Cos(angle), ring == 0 ? -halfThickness : halfThickness, doorRadius * Mathf.Sin(angle));
            }
        vertices[sides * 2] = new Vector3(0, -halfThickness, 0);
        vertices[sides * 2 + 1] = new Vector3(0, halfThickness, 0);
        int[] triangles = new int[sides * 12];
        int at = 0;
        for (int i = 0; i < sides; ++i)
        {
            int j = (i + 1) % sides;
            AddTriangle(triangles, ref at, i, sides + i, j);
            AddTriangle(triangles, ref at, j, sides + i, sides + j);
            AddTriangle(triangles, ref at, sides * 2, i, j);
            AddTriangle(triangles, ref at, sides * 2 + 1, sides + j, sides + i);
        }
        Vector2[] uv = new Vector2[vertices.Length];
        for (int i = 0; i < vertices.Length; ++i)
            uv[i] = new Vector2(0.5f + vertices[i].x / (doorRadius * 2), 0.5f + vertices[i].z / (doorRadius * 2));
        Mesh mesh = new Mesh();
        mesh.name = prefix + "_PressurePlate";
        mesh.vertices = vertices;
        mesh.triangles = triangles;
        mesh.uv = uv;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        door.AddComponent<MeshFilter>().sharedMesh = mesh;
        pressureRenderer = door.AddComponent<MeshRenderer>();
        Shader shader = Shader.Find("KSP/Diffuse") ?? Shader.Find("KSP/Unlit") ?? Shader.Find("Unlit/Color");
        if (shader == null)
            throw new InvalidOperationException("[Mk33FreeIVA] No opaque shader available for pressure hatch " + hatchId);
        Material material = new Material(shader);
        material.name = prefix + "_OpaqueMetal";
        material.color = new Color(0.82f, 0.85f, 0.87f, 1);
        Texture texture = GameDatabase.Instance.GetTexture("Mk33FreeIVA/Models/hatchGrey", false);
        if (texture != null) material.mainTexture = texture;
        material.renderQueue = 2000;
        pressureRenderer.sharedMaterial = material;
        pressureRenderer.shadowCastingMode = ShadowCastingMode.On;
        pressureRenderer.receiveShadows = true;

        // A primitive plate is deterministic and does not depend on PhysX
        // cooking the very thin convex .mu disc. Its corners lie in the fixed
        // pressure-frame wall; opening removes the whole plate and collider.
        pressureSeal = door.AddComponent<BoxCollider>();
        pressureSeal.isTrigger = false;
        pressureSeal.center = Vector3.zero;
        pressureSeal.size = new Vector3(doorRadius * 2, halfThickness * 2, doorRadius * 2);
        door.AddComponent<Mk33PressurePlateMarker>();

        // Geometry and native interaction keep their established v0.3.4
        // lifetime. Only the render-only decoration is replaced.
        classicVisualReady = TryCreateClassicVisual(prefix);
        for (int side = -1; !classicVisualReady && side <= 1; side += 2)
        {
            CreateHardware(prefix + "_HandleBar" + side, new Vector3(0, side * 0.065f, 0), new Vector3(0.34f, 0.025f, 0.09f), material);
            CreateHardware(prefix + "_HandleFootL" + side, new Vector3(-0.145f, side * 0.045f, 0), new Vector3(0.035f, 0.04f, 0.07f), material);
            CreateHardware(prefix + "_HandleFootR" + side, new Vector3(0.145f, side * 0.045f, 0), new Vector3(0.035f, 0.04f, 0.07f), material);
        }

        CreateHandle(prefix + "_HandleInside", 0.055f);
        CreateHandle(prefix + "_HandleOutside", -0.055f);
    }

    private bool TryCreateClassicVisual(string prefix)
    {
        const string modelPath = "FreeIva/Props/FreeIva_Hatch_Round_Size1";
        GameObject decoration = null;
        try
        {
            GameObject prefab = GameDatabase.Instance.GetModelPrefab(modelPath);
            if (prefab == null) throw new InvalidOperationException("installed FreeIVA Size1 model is missing");
            Transform source = FindVisualTransform(prefab.transform, "Hatch_Size1_Door");
            if (source == null) throw new InvalidOperationException("installed FreeIVA Size1 door is missing");
            MeshFilter leaf = source.GetComponent<MeshFilter>();
            if (leaf == null || leaf.sharedMesh == null || leaf.sharedMesh.vertexCount < 100)
                throw new InvalidOperationException("installed FreeIVA Size1 door mesh is incomplete");

            // The dependency's complete prefab contains an animation, cutout,
            // tube and physical colliders. Copy ONLY the leaf/handle renderer
            // meshes; none of those other objects become part of this hatch.
            // Bake against the model root to retain the closed pose, including
            // the leaf's hinge offset and its nested handle rotations.
            MeshRenderer[] sources = source.GetComponentsInChildren<MeshRenderer>(true);
            if (sources.Length < 3) throw new InvalidOperationException("installed FreeIVA Size1 handles are incomplete");
            decoration = new GameObject(prefix + "_ClassicVisual");
            decoration.layer = 20;
            decoration.transform.SetParent(pressureDoor, false);
            decoration.SetActive(false);
            float scale = doorRadius / 0.41f;
            Matrix4x4 modelInverse = prefab.transform.worldToLocalMatrix;
            foreach (MeshRenderer renderer in sources)
            {
                MeshFilter filter = renderer.GetComponent<MeshFilter>();
                if (filter == null || filter.sharedMesh == null || filter.sharedMesh.vertexCount == 0 ||
                    renderer.sharedMaterials.Length != filter.sharedMesh.subMeshCount)
                    throw new InvalidOperationException("installed FreeIVA Size1 visual/material is incomplete");
                foreach (Material material in renderer.sharedMaterials)
                    if (material == null || material.shader == null)
                        throw new InvalidOperationException("installed FreeIVA Size1 material is missing");
                Matrix4x4 pose = modelInverse * renderer.transform.localToWorldMatrix;
                Matrix4x4 normalPose = pose.inverse.transpose;
                Mesh mesh = UnityEngine.Object.Instantiate(filter.sharedMesh);
                mesh.name = prefix + "_Classic_" + renderer.name;
                Vector3[] vertices = mesh.vertices;
                for (int i = 0; i < vertices.Length; ++i)
                {
                    vertices[i] = pose.MultiplyPoint3x4(vertices[i]) * scale;
                    if (!FiniteVector(vertices[i]) || vertices[i].magnitude > doorRadius * 2)
                        throw new InvalidOperationException("installed FreeIVA Size1 visual has an unexpected pose");
                }
                mesh.vertices = vertices;
                Vector3[] normals = mesh.normals;
                for (int i = 0; i < normals.Length; ++i) normals[i] = normalPose.MultiplyVector(normals[i]).normalized;
                mesh.normals = normals;
                Vector4[] tangents = mesh.tangents;
                for (int i = 0; i < tangents.Length; ++i)
                {
                    Vector3 direction = pose.MultiplyVector(new Vector3(tangents[i].x, tangents[i].y, tangents[i].z)).normalized;
                    tangents[i] = new Vector4(direction.x, direction.y, direction.z, tangents[i].w * (pose.determinant < 0 ? -1 : 1));
                }
                mesh.tangents = tangents;
                if (pose.determinant < 0)
                    for (int sub = 0; sub < mesh.subMeshCount; ++sub)
                    {
                        int[] indices = mesh.GetTriangles(sub);
                        for (int i = 0; i < indices.Length; i += 3)
                        { int swap = indices[i + 1]; indices[i + 1] = indices[i + 2]; indices[i + 2] = swap; }
                        mesh.SetTriangles(indices, sub);
                    }
                mesh.RecalculateBounds();
                GameObject visual = new GameObject(prefix + "_Classic_" + renderer.name);
                visual.layer = 20;
                visual.transform.SetParent(decoration.transform, false);
                visual.AddComponent<MeshFilter>().sharedMesh = mesh;
                MeshRenderer copy = visual.AddComponent<MeshRenderer>();
                // Source texture, normal map, UVs and all material properties
                // are read-only shared assets; never change the dependency.
                copy.sharedMaterials = renderer.sharedMaterials;
                copy.shadowCastingMode = ShadowCastingMode.On;
                copy.receiveShadows = true;
            }
            // The classic model has a small central porthole. Give it an
            // opaque blue-gray insert so no IVA behind a closed pressure door
            // is visible. Only the render disc shrinks; the physical .545m
            // pressure seal and every surrounding collision remain unchanged.
            Mesh backing = pressureDoor.GetComponent<MeshFilter>().sharedMesh;
            Vector3[] backingVertices = backing.vertices;
            for (int i = 0; i < backingVertices.Length; ++i)
            {
                backingVertices[i].x *= 0.145f / doorRadius;
                backingVertices[i].z *= 0.145f / doorRadius;
            }
            backing.vertices = backingVertices;
            backing.RecalculateBounds();
            pressureRenderer.sharedMaterial.color = new Color(0.10f, 0.16f, 0.20f, 1);
            pressureRenderer.sharedMaterial.mainTexture = null;
            classicVisual = decoration.transform;
            decoration.SetActive(true);
            return true;
        }
        catch (Exception exception)
        {
            if (decoration != null) decoration.SetActive(false);
            Debug.LogWarning("[Mk33FreeIVA] Hatch " + hatchId + " keeps its opaque fallback: " + exception.Message + ".");
            return false;
        }
    }

    private static Transform FindVisualTransform(Transform root, string name)
    {
        if (root.name == name) return root;
        for (int i = 0; i < root.childCount; ++i)
        {
            Transform found = FindVisualTransform(root.GetChild(i), name);
            if (found != null) return found;
        }
        return null;
    }

    private static bool FiniteVector(Vector3 value)
    {
        return !Single.IsNaN(value.x) && !Single.IsInfinity(value.x) &&
            !Single.IsNaN(value.y) && !Single.IsInfinity(value.y) &&
            !Single.IsNaN(value.z) && !Single.IsInfinity(value.z);
    }

    private static void AddTriangle(int[] target, ref int at, int a, int b, int c)
    {
        target[at++] = a; target[at++] = b; target[at++] = c;
    }

    private void CreateHandle(string name, float y)
    {
        GameObject handle = new GameObject(name);
        handle.layer = 20;
        handle.transform.SetParent(transform, false);
        handle.transform.localPosition = new Vector3(0, y, 0);
        BoxCollider click = handle.AddComponent<BoxCollider>();
        click.isTrigger = false;
        click.size = new Vector3(0.36f, 0.025f, 0.14f);
    }

    private void CreateHardware(string name, Vector3 center, Vector3 size, Material material)
    {
        GameObject hardware = new GameObject(name);
        hardware.layer = 20;
        hardware.transform.SetParent(pressureDoor, false);
        hardware.transform.localPosition = center;
        Vector3[] vertices = new Vector3[8];
        for (int i = 0; i < 8; ++i)
            vertices[i] = new Vector3((i & 4) == 0 ? -size.x / 2 : size.x / 2, (i & 2) == 0 ? -size.y / 2 : size.y / 2, (i & 1) == 0 ? -size.z / 2 : size.z / 2);
        Mesh mesh = new Mesh();
        mesh.name = name;
        mesh.vertices = vertices;
        mesh.triangles = new[] { 0,1,3, 0,3,2, 4,6,7, 4,7,5, 0,4,5, 0,5,1, 2,3,7, 2,7,6, 0,2,6, 0,6,4, 1,5,7, 1,7,3 };
        mesh.RecalculateNormals(); mesh.RecalculateBounds();
        hardware.AddComponent<MeshFilter>().sharedMesh = mesh;
        hardware.AddComponent<MeshRenderer>().sharedMaterial = material;
    }

    public override void OnAwake()
    {
        // Awake may precede this module's OnLoad or native IVA registration.
        // Pending readiness is not a failed load and must not latch seat policy.
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
        if (!bootStarted) { ApplyPressureState(false); return; }
        if (part != null) walkGatePart = part;
        if (!loadReady)
        {
            ApplyPressureState(false);
            if (bootStarted && loadAttempted) DisableWalking("pressure hatch did not finish loading");
            return;
        }
        if (nativeAwakeAttempted)
        {
            DisableWalking("native initialization failed for this instance");
            return;
        }
        if (internalProp == null || internalModel == null || part == null || vessel == null ||
            InternalModuleFreeIva.GetForModel(internalModel) == null)
        {
            ApplyPressureState(false);
            return;
        }
        nativeAwakeAttempted = true;
        try { base.OnAwake(); }
        catch (Exception exception) { DisableWalking("native initialization failed: " + exception.Message); return; }
        flightInitialized = true;
        SetOpened(false, false);
        ApplyPressureState(false);
        Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
        Debug.Log("[Mk33FreeIVA] Pressure hatch " + hatchId + " initialized CLOSED in " + internalModel.internalName +
            "; plate=" + (pressureDoor != null) + "; collider=" + (pressureSeal != null && pressureSeal.enabled) +
            "; layer=" + (pressureSeal == null ? -1 : pressureSeal.gameObject.layer) + "; attach=" + attachNodeId + "; dock=" + dockingPortNodeName + "; EVA=" + airlockName + ".");
    }

    private void DisableWalking(string reason)
    {
        if (HighLogic.LoadedSceneIsFlight)
        {
            if (part != null) walkGatePart = part;
            Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, true, "pressure hatch '" + hatchId + "': " + reason);
        }
        ApplyPressureState(false);
    }

    private void OnDestroy()
    {
        Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
    }

    protected override void Open(bool open, bool allowSounds = true)
    {
        if (!loadReady || (HighLogic.LoadedSceneIsFlight && !flightInitialized)) { ApplyPressureState(false); return; }
        // Native remote-hatch synchronization also enters this virtual method.
        // Check the real attachment graph, not just the cached ConnectedHatch,
        // which can still point at a peer during an undocking refresh.
        if (open && (!Mk33FreeIvaConnection.HasCompleteShell(this) || (requireConnected && !CanEVA && !HasPhysicalConnection())))
        {
            open = false;
            if (!reportedInvalidConnection)
                Debug.LogWarning("[Mk33FreeIVA] Pressure hatch " + hatchId + " remains CLOSED: no valid physical connection.");
            reportedInvalidConnection = true;
        }
        base.Open(open, allowSounds);
        ApplyPressureState(IsOpen);
    }

    private void LateUpdate()
    {
        if (!HighLogic.LoadedSceneIsFlight) return;
        if (!flightInitialized) { TryInitializeRuntime(); if (!flightInitialized) return; }
        if (IsOpen && (IsBlockedByAnimation() || !Mk33FreeIvaConnection.HasCompleteShell(this) || (requireConnected && !CanEVA && !HasPhysicalConnection())))
            SetOpened(false, false);
        ApplyPressureState(IsOpen);
    }

    private void ApplyPressureState(bool open)
    {
        if (pressureDoor == null) return;
        pressureDoor.gameObject.SetActive(!open);
        if (pressureSeal != null)
        {
            pressureSeal.gameObject.layer = 16;
            pressureSeal.isTrigger = false;
            pressureSeal.enabled = !open;
        }
        if (!open && CameraManager.Instance != null && CameraManager.Instance.currentCameraMode == CameraManager.CameraMode.IVA)
            foreach (MeshRenderer renderer in pressureDoor.GetComponentsInChildren<MeshRenderer>(true))
                renderer.enabled = true;
        if (classicVisualReady && classicVisual != null)
            classicVisual.gameObject.SetActive(true);
    }

    private bool HasPhysicalConnection()
    {
        return Mk33FreeIvaConnection.IsPhysical(this);
    }
}

public static class Mk33FreeIvaConnection
{
    public static bool IsPhysical(FreeIvaHatch hatch)
    {
        FreeIvaHatch peer = hatch.ConnectedHatch;
        Part part = hatch.part;
        if (peer == null || part == null || peer.part == null || peer.vessel != hatch.vessel) return false;
        if ((peer is Mk33FreeIvaPressureHatch || peer is Mk33FreeIvaHatch) && !HasCompleteShell(peer)) return false;
        if (!String.IsNullOrEmpty(hatch.dockingPortNodeName))
        {
            foreach (PartModule candidate in part.Modules)
            {
                ModuleDockingNode dock = candidate as ModuleDockingNode;
                if (dock != null && dock.nodeTransformName == hatch.dockingPortNodeName)
                    return dock.state != null && dock.state.Contains("Docked") && dock.otherNode != null && dock.otherNode.part == peer.part;
            }
            return false;
        }
        AttachNode node = part.FindAttachNode(hatch.attachNodeId);
        Part previous = part;
        var seen = new HashSet<Part>();
        while (node != null && node.attachedPart != null && seen.Add(node.attachedPart))
        {
            Part next = node.attachedPart;
            AttachNode opposing = next.FindAttachNodeByPart(previous);
            if (next == peer.part)
                return opposing != null && opposing.id == peer.attachNodeId;
            ModuleFreeIva pass = next.GetComponent<ModuleFreeIva>();
            if (pass == null || opposing == null) return false;
            string exit = opposing.id == pass.passThroughNodeA ? pass.passThroughNodeB : opposing.id == pass.passThroughNodeB ? pass.passThroughNodeA : null;
            if (String.IsNullOrEmpty(exit)) return false;
            previous = next;
            node = next.FindAttachNode(exit);
        }
        return false;
    }

    public static bool HasCompleteShell(FreeIvaHatch hatch)
    {
        if (hatch.internalModel == null) return false;
        Transform shell = hatch.internalModel.transform.Find("Mk33Shell");
        Mk33ColliderMarker marker = shell == null ? null : shell.GetComponent<Mk33ColliderMarker>();
        return marker != null && marker.complete;
    }

}

// Checked before the source geometry is cut. A cloned pressure plate keeps the
// marker; a failed module load never authorizes an uncapped aperture.
public sealed class Mk33PressurePlateMarker : MonoBehaviour
{
    public bool complete;
}

// The new empty-capacity nose/probe interiors already contain authored solid
// colliders. Validate them in place, without copying them or running a cutter.
// This gives pressure hatches the same explicit readiness marker as original
// Mk-33 interiors whose collider shell is constructed by Mk33FreeIvaGeometry.
public sealed class Mk33FreeIvaAuthoredShell : InternalModule
{
    [SerializeField] private bool loadAttempted;
    [NonSerialized] private bool bootStarted;
    [NonSerialized] private Part walkGatePart;

    public override void OnLoad(ConfigNode node)
    {
        loadAttempted = true;
        try { LoadAuthoredShell(node); }
        catch (Exception exception)
        {
            Debug.LogError("[Mk33FreeIVA] Authored shell LOAD FAILED: " + exception.GetType().Name + ": " + exception.Message + ". Hatches remain closed; loading continues.");
        }
    }

    private void LoadAuthoredShell(ConfigNode node)
    {
        base.OnLoad(node);
        InternalModel model = internalModel ?? (internalProp == null ? null : internalProp.internalModel);
        if (model == null)
            throw new InvalidOperationException("[Mk33FreeIVA] Authored shell must be placed directly in INTERNAL.");
        Transform existing = model.transform.Find("Mk33Shell");
        Mk33ColliderMarker marker;
        if (existing != null)
        {
            marker = existing.GetComponent<Mk33ColliderMarker>();
            if (marker == null || !marker.authored)
                throw new InvalidOperationException("[Mk33FreeIVA] Authored shell cannot share another builder's readiness marker.");
            marker.complete = false;
            marker.sourceCount = 0;
        }
        else
        {
            GameObject markerObject = new GameObject("Mk33Shell");
            markerObject.transform.SetParent(model.transform, false);
            marker = markerObject.AddComponent<Mk33ColliderMarker>();
            marker.authored = true;
        }
        var names = new HashSet<string>(StringComparer.Ordinal);
        int count = 0;
        try
        {
            foreach (string sourceName in node.GetValues("sourceTransform"))
            {
                if (String.IsNullOrEmpty(sourceName) || !names.Add(sourceName))
                    throw new InvalidOperationException("An authored-shell source is missing or duplicated.");
                Transform source = FindNamed(model.transform, sourceName);
                if (source == null)
                    throw new InvalidOperationException("Authored shell transform '" + sourceName + "' was not found.");
                count += Mk33FreeIvaColliderSetup.PrepareImportedShell(source, "Authored shell '" + sourceName + "'");
            }
            if (count == 0)
                throw new InvalidOperationException("No authored shell colliders were configured.");
            marker.sourceCount = count;
            marker.complete = true;
            Debug.Log("[Mk33FreeIVA] " + model.internalName + ": validated " + count + " authored shell colliders in place.");
        }
        catch (Exception exception)
        {
            Debug.LogError("[Mk33FreeIVA] " + model.internalName + ": authored shell is INCOMPLETE: " + exception.Message);
        }
    }

    public override void OnAwake()
    {
        // Actual source validation belongs to OnLoad; Awake can run earlier.
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
        Transform shell = internalModel.transform.Find("Mk33Shell");
        Mk33ColliderMarker marker = shell == null ? null : shell.GetComponent<Mk33ColliderMarker>();
        if (marker != null && marker.complete)
            Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
        else if (loadAttempted)
            Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, true, "authored shell is incomplete in " + internalModel.internalName);
    }

    private void OnDestroy()
    {
        Mk33FreeIvaWalkGate.SetBlocked(walkGatePart, this, false, String.Empty);
    }

    private static Transform FindNamed(Transform root, string name)
    {
        if (root.name == name) return root;
        for (int i = 0; i < root.childCount; ++i)
        {
            Transform child = FindNamed(root.GetChild(i), name);
            if (child != null) return child;
        }
        return null;
    }
}

// KSP's .mu loader, including KSPCF 1.41.1 MuParser.ReadMeshCollider2,
// forces MeshCollider.convex=true and ignores the file's convex flag.
// Native FreeIVA changes imported passage shells back to nonconvex during its
// OnLoad. Our pre-cut checks run earlier, so do the same only for explicitly
// declared passage shells/tubes before validating their physical readiness.
public static class Mk33FreeIvaColliderSetup
{
    public static int PrepareImportedShell(Transform root, string context)
    {
        MeshCollider[] colliders = root == null ? new MeshCollider[0] : root.GetComponentsInChildren<MeshCollider>(true);
        if (colliders.Length == 0)
            throw new InvalidOperationException(context + " is missing or has no MeshCollider.");
        foreach (MeshCollider collider in colliders)
        {
            Mesh mesh = collider.sharedMesh;
            if (!collider.enabled || collider.isTrigger || collider.gameObject.layer != 16 ||
                mesh == null || mesh.vertexCount < 3 || mesh.triangles.Length < 3)
                throw new InvalidOperationException(context + " is not an enabled, nontrigger layer-16 mesh with readable geometry.");
        }
        foreach (MeshCollider collider in colliders)
            if (collider.convex) collider.convex = false;
        return colliders.Length;
    }

    public static void PrepareNamedTube(InternalModel model, string name)
    {
        if (String.IsNullOrEmpty(name)) return;
        if (model == null) throw new InvalidOperationException("Docking tube '" + name + "' has no INTERNAL model.");
        int occurrence = 0;
        int comma = name.LastIndexOf(',');
        string actual = name;
        if (comma >= 0)
        {
            if (!Int32.TryParse(name.Substring(comma + 1), out occurrence) || occurrence < 0)
                throw new InvalidOperationException("Invalid docking tube occurrence selector '" + name + "'.");
            actual = name.Substring(0, comma);
        }
        PrepareImportedShell(Find(model.transform, actual, ref occurrence), "Docking tube '" + name + "'");
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
}

// One owner cannot clear another module's protection. The original configured
// seat policy is restored only after our final owned block is released.
// This component is added to live parts only; it never rewrites part prefabs.
public sealed class Mk33FreeIvaWalkGate : MonoBehaviour
{
    private readonly HashSet<object> blockers = new HashSet<object>();
    private ModuleFreeIva module;
    private bool originalAllowsUnbuckling;
    private bool hasOriginalPolicy;

    public static void SetBlocked(Part part, object owner, bool blocked, string reason)
    {
        if (part == null || owner == null) return;
        Mk33FreeIvaWalkGate gate = part.GetComponent<Mk33FreeIvaWalkGate>();
        if (gate == null)
        {
            if (!blocked) return;
            gate = part.gameObject.AddComponent<Mk33FreeIvaWalkGate>();
        }
        gate.Bind(part.GetComponent<ModuleFreeIva>());
        gate.Change(owner, blocked, reason);
    }

    private void Bind(ModuleFreeIva replacement)
    {
        if (System.Object.ReferenceEquals(module, replacement)) return;
        module = replacement;
        hasOriginalPolicy = false;
        if (module != null && blockers.Count != 0)
        {
            originalAllowsUnbuckling = module.allowsUnbuckling;
            hasOriginalPolicy = true;
            if (module.allowsUnbuckling) module.allowsUnbuckling = false;
        }
    }

    private void Change(object owner, bool blocked, string reason)
    {
        if (module == null && blocked) return;
        if (blocked)
        {
            if (!hasOriginalPolicy)
            {
                originalAllowsUnbuckling = module.allowsUnbuckling;
                hasOriginalPolicy = true;
            }
            bool added = blockers.Add(owner);
            if (module.allowsUnbuckling) module.allowsUnbuckling = false;
            if (added) Debug.LogError("[Mk33FreeIVA] Walking blocked for this part: " + reason + ".");
        }
        else if (blockers.Remove(owner) && blockers.Count == 0)
        {
            if (module != null && hasOriginalPolicy && module.allowsUnbuckling != originalAllowsUnbuckling)
                module.allowsUnbuckling = originalAllowsUnbuckling;
            hasOriginalPolicy = false;
            Debug.Log("[Mk33FreeIVA] All owned walking blocks cleared; restored configured unbuckling policy.");
        }
    }
}
