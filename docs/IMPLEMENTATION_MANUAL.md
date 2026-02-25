# Doomguy Overlay Implementation Manual (Beginner-Friendly)

This is a practical, **step-by-step manual** for implementing the Doomguy face overlay end-to-end.

If you feel like you have “no idea what you are doing,” follow the checklist in order and do not skip steps.

---

## What you are building

You are connecting four parts:

1. **OBS scene** (captures game + overlay placement)
2. **Health relay** (extracts health % from game HUD)
3. **Server** (accepts health samples and resolves frame names)
4. **Overlay renderer** (shows `STF*.png` frame in OBS browser source)

The frame selection logic is already implemented in `doomguy_overlay_engine.py` via `DoomguyFaceEngine`.

---

## Prerequisites

Before starting, make sure you have:

- Python 3.10+
- OBS Studio
- This repository checked out locally
- A game with a visible health bar

Optional but recommended:

- `venv` for isolated Python dependencies
- A second monitor for calibration

---

## Step 1: Validate the repository locally

From the repo root:

```bash
python -m pytest -q
```

Expected result: all tests pass.

If tests fail, stop and fix your environment first before integrating OBS.

---

## Step 2: Understand the frame engine (already done for you)

You do **not** need to write frame-logic from scratch.

`DoomguyFaceEngine` already handles:

- health bucket mapping
- look cycling (`center -> left -> center -> right`)
- automatic pain pulses on health drop
- dead frame at `health_percent == 0`

Minimal example:

```python
from doomguy_overlay_engine import DoomguyFaceEngine

engine = DoomguyFaceEngine()
print(engine.update(100).frame_name)  # e.g. STFST01
print(engine.update(74).frame_name)   # may trigger pain or bucket frame
```

---

## Step 3: Create your OBS scene exactly once

Create a scene with **this exact name**:

- `HUD_CAPTURE_SCENE`

Add sources with **these exact names**:

1. `GAME_FEED`
2. `HEALTH_ROI_GUIDE` (optional, for setup)
3. `OVERLAY_FACE_OUTPUT` (Browser Source)

Why exact naming matters: your relay and debugging workflow depend on consistent names.

---

## Step 4: Define health ROI for your game

ROI = rectangle around health bar in OBS base-canvas pixel coordinates.

You need these values:

- `x`
- `y`
- `width`
- `height`

Calibration target:

- full health: ~95%+ fill in ROI
- near empty: <20% fill in ROI
- your color threshold must isolate bar fill from background

---

## Step 5: Create a game profile

Start from `config/game_profiles.example.json` and copy one profile.

For your game, set:

- `id`
- `obs_scene_name` (`HUD_CAPTURE_SCENE`)
- `health_roi`
- `fill_color_hsv` (low/high)
- `direction` (`left_to_right` or `right_to_left`)
- `smoothing_window` (start with `5`)
- `damage_drop_threshold` (start with `2`)

Do not tune everything at once. First get a stable health %, then tune damage threshold.

---

## Step 6: Send health samples to the server

Your relay should POST to:

- `POST /v1/health-sample`

At ~8–15 Hz with payload like:

```json
{
  "game_id": "apex",
  "timestamp_ms": 1737000000000,
  "health_percent": 73,
  "confidence": 0.94,
  "source": {
    "scene": "HUD_CAPTURE_SCENE",
    "roi": { "x": 120, "y": 980, "width": 320, "height": 24 }
  }
}
```

Rules to enforce before sending:

- clamp health to `0..100`
- include confidence score
- include game id and ROI metadata

---

## Step 7: Apply server-side acceptance rules

When receiving samples:

1. Ignore (or hold last value) when `confidence < 0.70`
2. If no fresh sample for ~600 ms, hold previous frame
3. On valid sample, call `engine.update(health_percent)`
4. Return/render `state.frame_name`

If your server has no data yet, default to healthy center frame (`STFST01`).

---

## Step 8: Expose overlay state for browser source

Provide endpoint:

- `GET /v1/face-state`

Return data similar to:

```json
{
  "frame": "STFST11",
  "health_percent": 73,
  "health_bucket": 1,
  "look": "center",
  "is_pain": false,
  "updated_at_ms": 1737000000100
}
```

In your browser source UI:

- poll at 8–15 Hz (or websocket push)
- render `<img src="/<frame>.png">`
- use nearest-neighbor / pixelated scaling

---

## Step 9: Wire OBS browser source

In `OVERLAY_FACE_OUTPUT` browser source settings:

- URL: your overlay UI endpoint
- Width/Height: set to desired output size
- Place and scale over HUD location in scene

Check that changing health in game changes frame image without visible lag.

---

## Step 10: Validate with a fixed test script

Run this checklist in-game:

1. Health at 100% -> healthy bucket frames (`STFST0x`)
2. Drop to ~75% -> bucket 1 frames (`STFST1x`)
3. Drop to ~50% -> bucket 2 frames (`STFST2x`)
4. Drop to ~25% -> bucket 3 frames (`STFST3x`)
5. Drop to ~10% -> bucket 4 frames (`STFST4x`)
6. Sudden hit -> pain frame appears briefly (`STFPAINx`)
7. Health 0 -> `STFDEAD0`

If one step fails, debug only that layer (ROI, relay, server, or renderer) before continuing.

---

## Step 11: Common beginner mistakes (and fixes)

- **Mistake:** ROI includes extra HUD elements.
  - **Fix:** tighten ROI and retune HSV range.
- **Mistake:** overlay flickers between frames.
  - **Fix:** increase smoothing window slightly (5 -> 7).
- **Mistake:** pain triggers constantly on tiny noise.
  - **Fix:** increase `damage_drop_threshold` (2 -> 3 or 4).
- **Mistake:** wrong look direction assumptions.
  - **Fix:** trust engine’s look sequence and verify with logged `look` field.
- **Mistake:** nothing updates in OBS.
  - **Fix:** verify browser source URL and server logs first.

---

## Step 12: Go-live checklist

Before streaming/recording:

- Tests pass locally
- ROI calibrated at 100/75/50/25/10
- Confidence stable during combat motion
- No frame freeze under normal network/CPU load
- Dead frame verified at 0 health
- Browser source aligned and sized correctly

If all six are true, your implementation is production-ready.

---

## Reference docs

- System contract: `docs/OBS_SCENE_AND_RELAY_SPEC.md`
- Engine module: `doomguy_overlay_engine.py`
- Profile template: `config/game_profiles.example.json`
