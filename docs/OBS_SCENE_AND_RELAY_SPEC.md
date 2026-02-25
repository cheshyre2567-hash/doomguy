# Doomguy Overlay: OBS Scene + Relay Specification

This document defines a consistent, game-agnostic contract for how OBS sends health information to a server and how the server selects Doomguy face frames.

## 1) OBS Scene Contract (required)

Create one OBS Scene named:

- `HUD_CAPTURE_SCENE`

Inside this scene add these sources (exact names):

1. `GAME_FEED` (game capture or window capture)
2. `HEALTH_ROI_GUIDE` (optional rectangle for setup only)
3. `OVERLAY_FACE_OUTPUT` (browser source that renders Doomguy frame)

### Health ROI (region of interest)

For each game, define one rectangular ROI that bounds the health bar:

- `x`, `y`, `width`, `height`
- coordinate space: pixels in base canvas resolution (for example 1920x1080)

During calibration, verify:

- At full health, at least 95% of ROI's bar pixels are filled.
- At near-empty health, under 20% of ROI's bar pixels are filled.
- Color threshold cleanly separates fill color from background.

## 2) Per-Game Profile (required)

Each game uses a profile object with:

- `id`: unique game key
- `obs_scene_name`: usually `HUD_CAPTURE_SCENE`
- Either simple fields:
  - `health_roi`: `x/y/width/height`
  - `fill_color_hsv`: low/high HSV threshold for the filled portion
- Or multi-bar fields:
  - `mode`: `segmented_stacked_bar`
  - `rois`: per-channel ROI map (`shield`, `health`, `lost_health`)
  - `channels`: per-channel HSV thresholds + semantics
  - `derived`: formula hints for choosing broadcast health
- `direction`: `left_to_right` or `right_to_left`
- `smoothing_window`: rolling sample count (recommended 5)
- `damage_drop_threshold`: minimum % drop to emit damage event (recommended 2)

See `config/game_profiles.example.json` for a canonical template.


### Multi-bar games (shield + health + recent damage)

Some games (like Arc Raiders) expose multiple bars:

- shield (blue)
- health (white)
- recently lost health (red chunk)

For these games, use `mode: "segmented_stacked_bar"` and define separate ROIs + HSV thresholds per channel in the profile.

Recommended behavior:

- Drive Doomguy frame selection from `health.percent` (`stream_health_percent_formula`).
- Optionally compute a separate survivability metric using shield+health for analytics.
- Treat red/lost-health as a semantic channel (`damage_recent`) and not as current health.

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
  "confidence": 0.94,
  "source": {
    "scene": "HUD_CAPTURE_SCENE",
    "roi": { "x": 120, "y": 980, "width": 320, "height": 24 }
  }
}
```

Rules:

- Clamp `health_percent` to 0-100.
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
