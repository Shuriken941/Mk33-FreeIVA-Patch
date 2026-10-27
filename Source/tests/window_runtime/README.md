# Window depth regression checks

`MK33_DOTNET=/path/to/dotnet python run.py` compiles and executes the exact
production `Mk33FreeIvaWindowMask.cs` with small KSP/Unity/FreeIVA dependency
doubles. It checks 30 geometry, failure, material ownership, lifecycle, camera
mode and native binding scenarios. It does not execute Unity or shader code.

The native FreeIVA shader is depth-only (`ColorMask 0`, `ZWrite On`). Its normal
queue is 1000; FreeIVA promotes the occupied IVA's opaque geometry to 999. The
helper now uses a private material at 998 for the **window geometry only**, so
anything behind that physical window is depth-tested even if it is drawn at
999. Original hull masks retain their native behavior. A window mask has no
collider and leaves hatch openings clear.

`python ../../source_checks/verify_window_depth.py --freeiva /path/to/FreeIva
--assets /path/to/Mk-33/Parts/SharedAssets` separately verifies installed source
geometry, configured aperture separation, exact upstream shader statements and
five simplified depth-composition cases. Its negative control demonstrates why
a depth-only pass cannot erase an IVA colour drawn earlier. This establishes an
ordering hazard; it does not identify the cause of the user's previous GPU
frame. No original meshes or textures are copied into this patch.

The production helper is also compiled against real KSP 1.12.5, Unity and
FreeIVA 0.2.20.2 API references. The complete assembly build remains `build.sh`.

In KSP, inspect every cockpit, Krew and Control Cab window while seated and
unbuckled, including during camera changes, after returning from EVA and after
vessel docking. The exterior world must remain visible; nearby IVA contents
must be hidden behind the window, and open hatch views must remain unobscured.
Repeat with the user's Deferred/Shabby configuration when installed.
