# Doomguy Overlay: OBS Scene + Relay Specification

This document defines a consistent, game-agnostic contract for how OBS sends health information to a server and how the server selects Doomguy face frames.

## 1) OBS Scene Contract (required)

Create one OBS Scene named:

- `HUD_CAPTURE_SCENE`

Inside this scene add these sources (exact names):

1. `GAME_FEED` (game capture or window capture)
2. `HEALTH_ROI_GUIDE` (optional rectangle for setup only)
3. `OVERLAY_FACE_OUTPUT` (browser source that renders Doomguy frame)


### Must this scene be active on stream?

`HUD_CAPTURE_SCENE` does **not** need to be your top-level live scene. It can run in the background **as long as OBS is rendering it**.

Recommended setup:

1. Build `HUD_CAPTURE_SCENE` with the required sources (`GAME_FEED`, `OVERLAY_FACE_OUTPUT`, etc.).
2. In your normal stream scene (for example `Live Scene`), add `HUD_CAPTURE_SCENE` as a **Scene Source**.
3. Keep that scene item visible (it can be cropped/scaled/positioned as needed).

If a scene is never rendered by OBS (not active and not referenced by an active scene), browser/script updates tied to that scene may pause depending on source settings.


### Source layout FAQ (important)

**Q1: Does `GAME_FEED` need to be the entire screen?**

No. It can be either:

- full game capture (recommended default), or
- a cropped capture focused around HUD areas.

The only hard requirement is that the configured `health_roi` coordinates correctly map to visible pixels for the health bar in the scene's canvas space.

**Q2: What is `HEALTH_ROI_GUIDE` in OBS sources?**

`HEALTH_ROI_GUIDE` is a helper source (usually a rectangle/shape) used during setup to visually mark the ROI area while you calibrate.

Recommended source type in OBS: **Color Source** named exactly `HEALTH_ROI_GUIDE`.

Quick add steps:

1. Sources -> `+` -> **Color Source**
2. Name: `HEALTH_ROI_GUIDE`
3. Use a visible color and partial opacity
4. Resize/move it to match the bar, then copy transform values

- It is optional.
- It should usually be hidden/removed for final live output.
- It does not drive logic by itself; your relay uses configured ROI coordinates.

**Q3: Must `OVERLAY_FACE_OUTPUT` be inside `HUD_CAPTURE_SCENE`?**

For this project contract, yes: keep `OVERLAY_FACE_OUTPUT` defined in `HUD_CAPTURE_SCENE` so naming and integration stay consistent.

If your top-level stream scene is `Live Scene`, include `HUD_CAPTURE_SCENE` there as a Scene Source. That way the overlay still appears in your live scene without duplicating configuration.

### Health ROI (region of interest)

For each game, define one rectangular ROI that bounds the health bar:

- `x`, `y`, `width`, `height`
- coordinate space: pixels in base canvas resolution (for example 1920x1080)


#### Practical calibration workflow (x/y/width/height + HSV)

1. Keep `GAME_FEED` in its final transform (same position/scale you stream with).
2. Use `HEALTH_ROI_GUIDE` to box only the health bar fill region.
3. Read the guide transform values from OBS and copy them to `health_roi`.
4. Sample filled bar pixels and choose `fill_color_hsv.low/high` bounds that include fill and exclude background.
5. Verify at full health and near-empty health before finalizing profile values.



OBS transform note:

- If OBS shows `Position/Size/Crop` instead of x/y/width/height labels, use the final displayed rectangle in canvas space as ROI values.
- Avoid rotated ROI guides for calibration; keep guide rotation at 0° and use an axis-aligned box even when the HUD bar itself is diagonal.

Note for angled HUD bars:

- ROI is still a standard axis-aligned rectangle in canvas space.
- Use the guide source transform values, not diagonal distance measurements.
- Include slight padding so fill detection remains stable under motion/compression.


Recommended compromise for slanted bars:

- Keep ROI axis-aligned, full bar length, and relatively thin.
- Add small padding (2-4 px), but avoid large top/bottom background capture.
- If noise persists, reduce ROI height first, then tighten HSV S/V bounds.

### Optional advanced mode: line-based sampling (recommended for slanted bars)

If your health bar is heavily diagonal or curved, line-based sampling is often more stable than rectangular ROI.

Define these fields in your game profile:

- `sampling_mode`: `"line"`
- `bar_start`: `{ "x": x1, "y": y1 }`
- `bar_end`: `{ "x": x2, "y": y2 }`
- `bar_thickness`: integer pixels (recommended 3-7)
- `line_samples`: number of steps along the bar (recommended 150-300, start 200)

How it works:

1. Compute direction vector from `bar_start` to `bar_end`.
2. Step along that vector for `line_samples` points.
3. At each step, sample a short perpendicular strip (`bar_thickness`).
4. Average HSV for the strip and classify `filled` vs `empty`.
5. Health % = `(index_of_last_filled_step / (line_samples - 1)) * 100`.

Benefits:

- Ignores most background above/below the bar.
- Works well with slanted bars where rectangle ROI includes too much noise.
- Keeps profile compact (two points + thickness).

Pseudocode:

```python
u = normalize(bar_end - bar_start)               # along-bar direction
n = perpendicular(u)                              # strip direction
last_filled = -1
for i in range(line_samples):
    t = i / (line_samples - 1)
    p = bar_start + u * (t * bar_length)
    hsv_avg = mean_hsv(sample_strip(center=p, normal=n, thickness=bar_thickness))
    if is_filled(hsv_avg, hsv_low, hsv_high):
        last_filled = i
health_percent = 0 if last_filled < 0 else round(100 * last_filled / (line_samples - 1))
```

During calibration, verify:

- At full health, at least 95% of ROI's bar pixels are filled.
- At near-empty health, under 20% of ROI's bar pixels are filled.
- Color threshold cleanly separates fill color from background.

## 2) Per-Game Profile (required)

Each game uses a profile object with:

- `id`: unique game key
- `obs_scene_name`: usually `HUD_CAPTURE_SCENE`
- `health_roi`: `x/y/width/height` (for `sampling_mode="roi"`, default)
- OR line mode fields: `bar_start`, `bar_end`, `bar_thickness`, optional `line_samples`
- `fill_color_hsv`: low/high HSV threshold for the filled portion
- `direction`: `left_to_right` or `right_to_left`
- `smoothing_window`: rolling sample count (recommended 5)
- `damage_drop_threshold`: minimum % drop to emit damage event (recommended 2)
- `hud_anchor` (optional): fixed pixel gate `{x,y,color_bgr,tolerance}` used to detect if HUD is visible.

See `config/game_profiles.example.json` for a canonical template.

## 3) Relay Payload OBS -> Server (required)

Emit health samples to server at 8-15 Hz.

Endpoint:

- `POST /v1/health-sample`

Payload:

```json
{
  "game_id": "apex",
  "timestamp_ms": 1737000000000,
  "health_percent": 73,
  "hud_anchor_visible": true,
  "confidence": 0.94,
  "source": {
    "scene": "HUD_CAPTURE_SCENE",
    "roi": { "x": 120, "y": 980, "width": 320, "height": 24 }
  }
}
```

Rules:

- Clamp `health_percent` to 0-100.
- If `hud_anchor_visible` is false, renderer may hide the face entirely.
- If `confidence < 0.70`, server should ignore sample (or hold last good value).
- Missing sample timeout: 600 ms; hold previous frame.

## 4) Server Frame Selection Rules (required)

### Health buckets

- `STFST00/01/02` => health >= 80
- `STFST10/11/12` => 60-79
- `STFST20/21/22` => 40-59
- `STFST30/31/32` => 20-39
- `STFST40/41/42` => 1-19
- `STFDEAD0` => 0

### Look direction mapping

- `0` => left
- `1` => center
- `2` => right

Default idle sequence (loop):

- center -> left -> center -> right -> repeat

### Damage reaction (pain)

If current smoothed health drops by at least `damage_drop_threshold` from previous sample, emit pain frame immediately:

- left look: `STFPAIN0`
- center look: `STFPAIN1`
- right look: `STFPAIN2`

Pain frame duration:

- hold for 2-3 animation ticks (recommended 3)
- after hold, return to bucket frame using current health + current look

## 5) Overlay Output Contract Server -> Browser Source

Endpoint:

- `GET /v1/face-state`

Response:

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

Browser source behavior:

- Poll at 8-15 Hz (or use websocket push).
- Render `<img src="/<frame>.png">`.
- Use nearest-neighbor scaling for retro pixel feel.

## 6) Adaptation checklist for new games

1. Copy a profile in `config/game_profiles.example.json`.
2. Set ROI from OBS canvas coordinates.
3. Tune HSV thresholds until confidence is stable.
4. Validate health values at 100%, 75%, 50%, 25%, 10%.
5. Confirm pain triggers on sudden drops.
6. Confirm dead frame appears only at 0.

## 7) Failure handling

- If confidence is low for >2 seconds, freeze last rendered frame.
- If server has no data yet, start at `STFST01` (healthy center look).
- If game profile is missing, reject with 400 and list available profiles.

## 8) Running a practical local relay loop (reference)

Reference scripts included in this repo:

1. `python examples/local_overlay_server.py`
   - Serves `/overlay`, `GET /v1/face-state`, and `POST /v1/health-sample`.
2. `python examples/obs_to_overlay_relay.py --profile <profile_id>`
   - Reads `GAME_FEED` from OBS via obs-websocket and POSTs health samples.

Dependencies for relay script:

```bash
pip install obsws-python opencv-python numpy requests
```

OBS websocket configuration is read from env vars:

- `OBS_HOST` (default `127.0.0.1`)
- `OBS_PORT` (default `4455`)
- `OBS_PASSWORD` (default empty)

