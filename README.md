# Doomguy Face Overlay Engine

This repository now includes:

- PNG face assets (`STFST*`, `STFPAIN*`, etc.)
- A reusable state engine (`doomguy_overlay_engine.py`) that maps health + damage into a frame name
- A strict OBS + relay integration specification (`docs/OBS_SCENE_AND_RELAY_SPEC.md`)
- Example multi-game profile config (`config/game_profiles.example.json`)

## Quick usage

```python
from doomguy_overlay_engine import DoomguyFaceEngine

engine = DoomguyFaceEngine()

state = engine.update(100)  # -> STFST01 (healthy, center)
state = engine.update(75)   # damage drop triggers pain frame based on look direction
print(state.frame_name)
```

## Run tests

```bash
python -m pytest -q
```

## Integration flow summary

1. OBS scene captures game HUD.
2. Health ROI is sampled and converted to `health_percent`.
3. Relay sends samples to your server (`POST /v1/health-sample`).
4. Server uses `DoomguyFaceEngine` to resolve current frame.
5. Browser source renders that frame PNG.

For full setup and internal coordination standards, read `docs/OBS_SCENE_AND_RELAY_SPEC.md`.
