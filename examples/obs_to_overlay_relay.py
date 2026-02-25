"""OBS -> Health Relay -> Doomguy overlay bridge.

This example reads pixels from OBS `HUD_CAPTURE_SCENE` (recommended), estimates
health_percent from either:
- rectangular ROI sampling, or
- line-based sampling (recommended for diagonal bars)

Then it posts health samples to a local overlay server:
    POST http://127.0.0.1:8765/v1/health-sample

Dependencies:
    pip install obsws-python opencv-python numpy requests

OBS prerequisites:
1) Enable obs-websocket in OBS (Tools -> WebSocket Server Settings)
2) Set host/port/password below (or via env vars)
3) Ensure `HUD_CAPTURE_SCENE` (or your chosen source) is visible in rendered scene graph

Run:
    python examples/obs_to_overlay_relay.py --profile game-example-line
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np
import obsws_python as obs
import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = ROOT / "config" / "game_profiles.example.json"


def clamp_health(value: float) -> int:
    return int(max(0, min(100, round(value))))


def decode_obs_data_url(data_url: str) -> np.ndarray:
    # Format: data:image/png;base64,AAAA...
    b64 = data_url.split(",", 1)[1]
    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return bgr


def hsv_mask_ratio(hsv_img: np.ndarray, low: list[int], high: list[int]) -> float:
    low_np = np.array(low, dtype=np.uint8)
    high_np = np.array(high, dtype=np.uint8)
    mask = cv2.inRange(hsv_img, low_np, high_np)
    return float(mask.mean() / 255.0)


def estimate_health_roi(frame_bgr: np.ndarray, profile: dict) -> tuple[int, float]:
    roi = profile["health_roi"]
    x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]
    crop = frame_bgr[y : y + h, x : x + w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    low = profile["fill_color_hsv"]["low"]
    high = profile["fill_color_hsv"]["high"]
    low_np = np.array(low, dtype=np.uint8)
    high_np = np.array(high, dtype=np.uint8)
    mask = cv2.inRange(hsv, low_np, high_np)

    # Project mask along bar direction.
    direction = profile.get("direction", "left_to_right")
    col_fill = (mask > 0).mean(axis=0)
    thresh = 0.25
    filled_cols = np.where(col_fill > thresh)[0]

    if len(filled_cols) == 0:
        return 0, 0.6

    if direction == "right_to_left":
        rightmost = int(filled_cols.max())
        health = 100.0 * ((w - 1 - rightmost) / max(1, w - 1))
    else:
        rightmost = int(filled_cols.max())
        health = 100.0 * (rightmost / max(1, w - 1))

    confidence = float(max(0.0, min(1.0, mask.mean() / 255.0 * 1.5)))
    return clamp_health(health), confidence


def sample_strip_hsv(frame_hsv: np.ndarray, center: np.ndarray, normal: np.ndarray, half_t: int) -> np.ndarray:
    pts = []
    for k in range(-half_t, half_t + 1):
        p = center + normal * k
        x = int(round(p[0]))
        y = int(round(p[1]))
        if 0 <= x < frame_hsv.shape[1] and 0 <= y < frame_hsv.shape[0]:
            pts.append(frame_hsv[y, x])
    if not pts:
        return np.array([0, 0, 0], dtype=np.float32)
    return np.mean(np.array(pts, dtype=np.float32), axis=0)


def estimate_health_line(frame_bgr: np.ndarray, profile: dict) -> tuple[int, float]:
    s = np.array([profile["bar_start"]["x"], profile["bar_start"]["y"]], dtype=np.float32)
    e = np.array([profile["bar_end"]["x"], profile["bar_end"]["y"]], dtype=np.float32)
    n_samples = int(profile.get("line_samples", 200))
    thickness = int(profile.get("bar_thickness", 5))

    v = e - s
    length = float(np.linalg.norm(v))
    if length < 1.0:
        return 0, 0.0
    u = v / length
    n = np.array([-u[1], u[0]], dtype=np.float32)

    frame_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    low = np.array(profile["fill_color_hsv"]["low"], dtype=np.float32)
    high = np.array(profile["fill_color_hsv"]["high"], dtype=np.float32)

    filled = []
    half_t = max(1, thickness // 2)

    for i in range(n_samples):
        t = i / max(1, (n_samples - 1))
        p = s + u * (t * length)
        hsv_avg = sample_strip_hsv(frame_hsv, p, n, half_t)
        is_filled = np.all(hsv_avg >= low) and np.all(hsv_avg <= high)
        filled.append(bool(is_filled))

    filled_indices = [i for i, val in enumerate(filled) if val]
    if not filled_indices:
        return 0, 0.55

    direction = profile.get("direction", "left_to_right")
    if direction == "right_to_left":
        first = min(filled_indices)
        health = 100.0 * ((n_samples - 1 - first) / max(1, n_samples - 1))
    else:
        last = max(filled_indices)
        health = 100.0 * (last / max(1, n_samples - 1))

    confidence = float(sum(filled) / max(1, n_samples))
    return clamp_health(health), confidence


def load_profile(path: Path, profile_id: str) -> dict:
    obj = json.loads(path.read_text())
    for p in obj.get("profiles", []):
        if p.get("id") == profile_id:
            return p
    ids = [p.get("id") for p in obj.get("profiles", [])]
    raise ValueError(f"Profile '{profile_id}' not found. Available: {ids}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Profile id in config/game_profiles.example.json")
    ap.add_argument("--profile-path", default=str(DEFAULT_PROFILE_PATH))
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--overlay-url", default="http://127.0.0.1:8765/v1/health-sample")
    ap.add_argument(
        "--source-name",
        default="HUD_CAPTURE_SCENE",
        help=(
            "OBS scene/source to screenshot. Use your full scene (e.g. HUD_CAPTURE_SCENE) "
            "for stable canvas-space coordinates."
        ),
    )
    ap.add_argument("--image-width", type=int, default=0, help="Screenshot width (must be >=8). 0 = auto")
    ap.add_argument("--image-height", type=int, default=0, help="Screenshot height (must be >=8). 0 = auto")
    args = ap.parse_args()

    profile = load_profile(Path(args.profile_path), args.profile)
    source_name = args.source_name

    obs_host = os.getenv("OBS_HOST", "127.0.0.1")
    obs_port = int(os.getenv("OBS_PORT", "4455"))
    obs_password = os.getenv("OBS_PASSWORD", "")

    client = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=5)

    scene_name = profile.get("obs_scene_name", "HUD_CAPTURE_SCENE")
    # OBS websocket requires imageWidth/imageHeight >= 8 for GetSourceScreenshot.
    if args.image_width >= 8 and args.image_height >= 8:
        shot_w, shot_h = args.image_width, args.image_height
    else:
        video = client.get_video_settings()
        base_w = getattr(video, "base_width", getattr(video, "baseWidth", 1920))
        base_h = getattr(video, "base_height", getattr(video, "baseHeight", 1080))
        shot_w = max(8, int(base_w))
        shot_h = max(8, int(base_h))
        if source_name != scene_name:
            print(
                "WARNING: auto screenshot size uses OBS base canvas. If --source-name is a "
                "sub-source (for example GAME_FEED), coordinates are in resized screenshot "
                "space and may feel off. Prefer --source-name "
                f"{scene_name} or pass explicit --image-width/--image-height."
            )

    period = 1.0 / max(1.0, args.fps)
    print(
        f"Relay started: profile={args.profile}, sampling_mode={profile.get('sampling_mode', 'roi')}, "
        f"source={source_name}, screenshot={shot_w}x{shot_h}"
    )

    while True:
        try:
            shot = client.get_source_screenshot(source_name, "png", shot_w, shot_h, 100)
        except Exception as exc:
            msg = str(exc)
            if "imageWidth" in msg or "minimum of `8" in msg:
                raise RuntimeError(
                    "OBS rejected screenshot size. Use --image-width/--image-height >= 8, "
                    "or omit them to auto-use OBS base resolution."
                ) from exc
            raise

        frame_bgr = decode_obs_data_url(shot.image_data)

        mode = profile.get("sampling_mode", "roi")
        if mode == "line":
            health, confidence = estimate_health_line(frame_bgr, profile)
        else:
            health, confidence = estimate_health_roi(frame_bgr, profile)

        payload = {
            "game_id": profile["id"],
            "timestamp_ms": int(time.time() * 1000),
            "health_percent": health,
            "confidence": round(float(confidence), 3),
            "source": {"scene": scene_name},
        }

        requests.post(args.overlay_url, json=payload, timeout=1.0)
        print(f"health={health:3d} confidence={confidence:.2f}")
        time.sleep(period)


if __name__ == "__main__":
    main()
