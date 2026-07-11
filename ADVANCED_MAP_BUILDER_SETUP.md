# Advanced Map Analyzer + Roblox Map Reconstruction

The map builder is now the primary pipeline.

```text
Reference video
→ sample frames
→ detect floors, walls, corridors, platforms and palette
→ estimate camera travel and map openness
→ create map requirements
→ generate connected platform/room graph
→ validate jump gaps, clearance and collisions
→ repair common layout problems
→ compile a richer Roblox map
→ open Studio
```

Run:

```powershell
py app.py
```

Review detection first:

```text
http://127.0.0.1:5000/map-analyzer
```

Then generate:

```text
http://127.0.0.1:5000/creator-ai-v2
```

The builder now creates evidence-driven platform proportions, connected bridges,
intentional jump gaps, transformation zones, indoor wall/ceiling shells,
railings, scene props, hazards, palette-derived colors, an action-linked player
path, and deterministic playability repairs.

Boundary: a single gameplay video cannot reveal hidden geometry or exact Roblox
stud dimensions. This reconstructs a playable map from visible evidence and
proportions; it is not neural 3D reconstruction yet.
