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


## Quick FAQ: Does `HUD_CAPTURE_SCENE` have to be the live scene?

No. It does **not** have to be your stream's top-level scene. You can keep using your existing `Live Scene`.

Use this pattern:

1. Build `HUD_CAPTURE_SCENE` once (with the required source names).
2. Add `HUD_CAPTURE_SCENE` into `Live Scene` as a **Scene Source**.
3. Keep it visible so OBS continues rendering/updating it.

In short: it can run in the background, but it must still be part of the currently rendered scene graph.

---


## Quick FAQ: Source setup details

### Does `GAME_FEED` have to be full-screen?

No. You can use either full-screen game capture or a cropped capture.

Rule: whatever you choose, your ROI coordinates must still point to the health bar correctly in OBS canvas coordinates.

### What is `HEALTH_ROI_GUIDE` in the source list?

It is a visual setup aid (rectangle/shape) to help you place and verify the health ROI during calibration.

**Recommended OBS source type:** `Color Source` (best default)

How to add it in OBS:

1. In `HUD_CAPTURE_SCENE`, click `+` in **Sources**.
2. Choose **Color Source**.
3. Name it exactly `HEALTH_ROI_GUIDE`.
4. Pick a bright color (green/magenta), set opacity around 25-40% so you can still see the HUD under it.
5. Resize/move it to cover the health bar fill region.
6. Right-click it -> **Transform** -> **Edit Transform** and copy Left/Top/Width/Height into your profile.

Alternative source types also work (for example `Image` with a transparent rectangle), but `Color Source` is simplest for most users.

- optional source
- usually hidden in production
- not used directly by the engine; it is for humans during setup

### Does `OVERLAY_FACE_OUTPUT` have to be on `HUD_CAPTURE_SCENE`?

For the documented contract, yes. Keep it in `HUD_CAPTURE_SCENE`.

If you stream from `Live Scene`, add `HUD_CAPTURE_SCENE` into `Live Scene` as a Scene Source. This gives you the overlay in your live output while keeping one canonical place to configure sources.

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

### Exact method: how to find `x`, `y`, `width`, `height`, and HSV

Use this quick process once you can see your game in OBS:

1. In OBS, set your base canvas (for example 1920x1080) and make sure `GAME_FEED` is positioned exactly how it will be used live.
2. Turn on/add `HEALTH_ROI_GUIDE` (a rectangle shape). Move and resize it until it tightly covers only the health bar fill area.
3. Open **Edit Transform** on `HEALTH_ROI_GUIDE` and copy the rectangle values:
   - `x` = Left
   - `y` = Top
   - `width`
   - `height`
4. Put those numbers into `health_roi` in your game profile.
5. Determine bar direction:
   - if the bar empties left-to-right, use `left_to_right`
   - if the bar empties right-to-left, use `right_to_left`
6. Determine HSV for the filled color:
   - take a screenshot frame where health bar fill is clearly visible
   - sample 5-10 pixels from the **filled** part of the bar
   - convert sampled RGB values to HSV
   - set `fill_color_hsv.low` slightly below minimum sampled H/S/V
   - set `fill_color_hsv.high` slightly above maximum sampled H/S/V
7. Validate threshold quality:
   - at 100% health, threshold should detect ~95%+ of bar fill
   - at near empty, threshold should detect <20%
   - if background noise is detected, tighten S/V bounds first
8. Run live checks at 100/75/50/25/10 health and adjust bounds in small increments.

Starter HSV strategy (when unsure):

- Red bars: start near `low=[0,120,70]`, `high=[10,255,255]`
- Green bars: start near `low=[45,80,80]`, `high=[90,255,255]`

Then tune to your game UI lighting/effects.


### OBS "Edit Transform" field mapping (when you do not see x/y/width/height labels)

Some OBS versions show these labels instead:

- `Position` -> corresponds to top-left placement (`x`, `y`)
- `Size` -> corresponds to displayed width/height after transform
- `Crop Left/Right/Top/Bottom` -> trims the source area
- `Rotation` -> rotates the source (avoid this for ROI calibration)

For this project, keep ROI calibration simple and reliable:

1. Set `HEALTH_ROI_GUIDE` rotation to `0.0` while capturing ROI values.
2. Use an axis-aligned rectangle that covers the slanted bar region.
3. Copy ROI from the guide's final top-left and size in canvas space.
4. If you used crop on a full-screen color source, copy the **final displayed rectangle** (not the original 1920x1080 source size).

If the bar is diagonal, that is OK: your ROI rectangle should be the smallest axis-aligned box that contains the bar fill.

### If your health bar is angled/slanted on screen (important)

In your screenshot, the bar appears slightly diagonal. Your `health_roi` is still an **axis-aligned rectangle** (`x`, `y`, `width`, `height`) in canvas coordinates.

Use this method:

1. Do **not** use the diagonal line length as ROI width.
2. Position `HEALTH_ROI_GUIDE` as a normal rectangle that fully contains the fill region across the whole bar.
3. Use **Edit Transform** values from the guide (Left/Top/Width/Height) as your ROI values.
4. Keep a small margin (2-4 px) around the fill so camera shake/compression does not clip detection.
5. If the slant causes extra background noise, tighten HSV S/V bounds and reduce ROI height slightly.


Practical recommendation for your exact case (diagonal bar + cropped color source):

- Do **not** rotate `HEALTH_ROI_GUIDE` for measurement. Keep rotation at 0°.
- Build a thin axis-aligned rectangle around the bar (include small 2-4 px padding).
- If background leaks into the ROI, keep narrowing ROI height and tighten HSV S/V bounds.
- The ROI does not need to match the bar angle; HSV thresholding handles the diagonal fill inside the rectangle.


### Middle ground for slanted bars (when tight ROI adds too much background)

If a perfectly tight box is impossible because the bar is diagonal, use this compromise:

1. Keep ROI axis-aligned and centered on the bar.
2. Make ROI **long enough** to include full bar length.
3. Make ROI **thin**: start around 1.5x to 2.0x the bar fill thickness.
4. Keep only small vertical padding (2-4 px), not large top/bottom margins.
5. Prefer extra width over extra height (height noise hurts more than width noise).
6. Tighten HSV saturation/value limits first if rocks/grass/UI edges leak into mask.

Practical target metrics:

- Full health: detected fill ratio roughly 0.85-0.98 inside ROI
- Near empty: detected fill ratio under ~0.20
- Idle/no-hit moments: frame should be stable (no constant pain flicker)

If you still get noisy detection, reduce ROI height by a few pixels and retest before changing width.

Quick sanity check:

- At full health, mask should cover nearly all fill segments.
- At low health, mask should shrink cleanly from the configured direction (`left_to_right` or `right_to_left`).

---

### Alternative for diagonal bars: line-based sampling (best-practice option)

If your relay supports it, this is usually the best method for slanted bars.

Instead of rectangle ROI dimensions, define:

- `BAR_START = (x1, y1)`
- `BAR_END = (x2, y2)`
- `BAR_THICKNESS = 3..7`
- optional `LINE_SAMPLES = 200`

Then:

1. Sample along `BAR_START -> BAR_END` in equal increments.
2. At each point, sample a tiny perpendicular strip (`BAR_THICKNESS`).
3. Compute average HSV and classify filled/empty.
4. Last filled sample index / total samples = health %.

Why this helps:

- It follows bar direction directly.
- It minimizes background contamination from the top/bottom area.
- It is more stable for angled HUD bars than large rectangular ROI.

Suggested starting values:

- `BAR_THICKNESS`: 5 px
- `LINE_SAMPLES`: 200
- HSV thresholds: same process as rectangle mode (sample filled pixels first).

## Step 5: Create a game profile

Start from `config/game_profiles.example.json` and copy one profile.

For your game, set:

- `id`
- `obs_scene_name` (`HUD_CAPTURE_SCENE`)
- `health_roi` (ROI mode), or line fields `bar_start`/`bar_end`/`bar_thickness`
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

## Step 13: Run a minimal local server and connect OBS

If you want a working local baseline before building your full relay, use:

```bash
python examples/local_overlay_server.py
```

This starts:

- Overlay page: `http://127.0.0.1:8765/overlay`
- Face state endpoint: `GET /v1/face-state`
- Health ingest endpoint: `POST /v1/health-sample`

OBS setup:

1. Open your `OVERLAY_FACE_OUTPUT` Browser Source.
2. Set URL to `http://127.0.0.1:8765/overlay`.
3. Keep source visible in the rendered scene graph.

Quick health test from terminal:

```bash
curl -X POST http://127.0.0.1:8765/v1/health-sample \
  -H 'Content-Type: application/json' \
  -d '{"game_id":"local","health_percent":100,"confidence":0.95}'

curl -X POST http://127.0.0.1:8765/v1/health-sample \
  -H 'Content-Type: application/json' \
  -d '{"game_id":"local","health_percent":60,"confidence":0.95}'

curl -X POST http://127.0.0.1:8765/v1/health-sample \
  -H 'Content-Type: application/json' \
  -d '{"game_id":"local","health_percent":25,"confidence":0.95}'
```

You should see the Doomguy frame update in OBS as health changes.

---


## Step 14: Read from OBS `GAME_FEED` and transmit health automatically

Use the provided bridge script:

```bash
pip install obsws-python opencv-python numpy requests
python examples/obs_to_overlay_relay.py --profile game-example-line
```

What it does:

1. Connects to OBS via obs-websocket.
2. Pulls screenshots from `GAME_FEED` at ~10 FPS.
3. Computes `health_percent` using your profile (`roi` mode or `line` mode).
4. Sends samples to `POST http://127.0.0.1:8765/v1/health-sample`.

Required sequence:

1. Start OBS and enable obs-websocket.
2. Start `python examples/local_overlay_server.py`.
3. Start relay bridge script above.
4. Set `OVERLAY_FACE_OUTPUT` Browser Source URL to `http://127.0.0.1:8765/overlay`.

Environment variables for OBS websocket (if needed):

```bash
export OBS_HOST=127.0.0.1
export OBS_PORT=4455
export OBS_PASSWORD='your_password'
```

Troubleshooting:

- If relay cannot connect, verify OBS websocket is enabled and port/password are correct.
- If you get `GetSourceScreenshot ... imageWidth ... minimum of 8`, use updated script defaults or pass `--image-width 1920 --image-height 1080`.
- If health is noisy, switch to `sampling_mode: "line"` and tune `bar_thickness` + HSV.
- If overlay does not update, test `GET http://127.0.0.1:8765/v1/face-state` in browser.

---

