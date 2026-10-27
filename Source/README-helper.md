# Helper architecture

See [README.md](README.md) for the current 0.3.5 architecture and build commands.
Pressure doors are generated directly before source cuts; original and authored
shell validation share a complete-shell marker. Native FreeIVA still owns hatch
connection discovery, normal interaction and tube scaling.

The old CircularHatch model remains a source-art example, not an active PROP in
the 0.3.0 configuration. Its exported-mesh check does not test the new runtime
pressure plate. Exact production state/geometry logic is exercised separately
by tests/pressure_runtime with dependency doubles, not the actual game.
