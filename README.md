# Doomguy Face Overlay Engine

This repository now includes:

- PNG face assets (`STFST*`, `STFOUCH*`, etc.)
- A reusable state engine (`doomguy_overlay_engine.py`) that maps health + damage into a frame name
- A strict OBS + relay integration specification (`docs/OBS_SCENE_AND_RELAY_SPEC.md`)
- Example multi-game profile config (`config/game_profiles.example.json`)

## Quick usage

```python
from doomguy_overlay_engine import DoomguyFaceEngine

engine = DoomguyFaceEngine()

state = engine.update(100)  # -> STFST01 (healthy, center)
state = engine.update(75)   # damage drop triggers STFOUCH frame based on health bucket
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

For a beginner-friendly step-by-step implementation guide, read `docs/IMPLEMENTATION_MANUAL.md`.

For full setup and internal coordination standards, read `docs/OBS_SCENE_AND_RELAY_SPEC.md`.

## Local end-to-end demo (OBS Browser Source + relay)

Run a minimal local relay/overlay server:

```bash
python examples/local_overlay_server.py
```

Then:

1. Set OBS Browser Source (`OVERLAY_FACE_OUTPUT`) URL to `http://127.0.0.1:8765/overlay`.
2. Send health samples to `POST http://127.0.0.1:8765/v1/health-sample`.

Example test sample:

```bash
curl -X POST http://127.0.0.1:8765/v1/health-sample \
  -H 'Content-Type: application/json' \
  -d '{"game_id":"local","health_percent":73}'
```


## Run OBS -> relay -> overlay end-to-end

1. Start local overlay server:

```bash
python examples/local_overlay_server.py
```

2. Enable OBS WebSocket (Tools -> WebSocket Server Settings).

3. Start OBS relay bridge (reads `HUD_CAPTURE_SCENE` by default, computes health, POSTs to server):

```bash
pip install obsws-python opencv-python numpy requests
python examples/obs_to_overlay_relay.py --profile game-example-line
```

For coordinate sanity, keep screenshots on scene-canvas space by sampling the scene (default):

```bash
python examples/obs_to_overlay_relay.py --profile game-example-line --source-name HUD_CAPTURE_SCENE
```


For coordinate calibration debugging, run the 30-second overlay helper (writes `debug_last_frame.png` with start/end markers and line):

```bash
python examples/obs_to_overlay_debug.py --profile game-example-line
```

If you previously saw `GetSourceScreenshot ... imageWidth ... minimum of 8`, pull latest code and rerun.
This script now auto-uses OBS base resolution. You can also force size explicitly:

```bash
python examples/obs_to_overlay_relay.py --profile game-example-line --image-width 1920 --image-height 1080
```

4. In OBS Browser Source `OVERLAY_FACE_OUTPUT`, set URL:

```text
http://127.0.0.1:8765/overlay
```

If OBS websocket needs password/host/port, set env vars:

```bash
export OBS_HOST=127.0.0.1
export OBS_PORT=4455
export OBS_PASSWORD='your_password'
```
