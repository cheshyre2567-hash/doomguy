"""OBS screenshot debugger for bar coordinate calibration.

Captures frames from OBS for 30 seconds, overlays bar start/end markers from a
profile, and writes `debug_last_frame.png` repeatedly (final frame persists).

Run:
    python examples/obs_to_overlay_debug.py --profile game-example-line
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

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = ROOT / "config" / "game_profiles.example.json"


def decode_obs_data_url(data_url: str) -> np.ndarray:
    b64 = data_url.split(",", 1)[1]
    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return bgr


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
    ap.add_argument("--duration-sec", type=float, default=30.0, help="How long to capture debug overlays")
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument(
        "--source-name",
        default="",
        help="OBS scene/source to screenshot. Empty uses profile obs_scene_name.",
    )
    ap.add_argument("--image-width", type=int, default=0, help="Screenshot width (must be >=8). 0 = auto")
    ap.add_argument("--image-height", type=int, default=0, help="Screenshot height (must be >=8). 0 = auto")
    args = ap.parse_args()

    profile = load_profile(Path(args.profile_path), args.profile)
    scene_name = profile.get("obs_scene_name", "HUD_CAPTURE_SCENE")
    source_name = args.source_name or scene_name

    obs_host = os.getenv("OBS_HOST", "127.0.0.1")
    obs_port = int(os.getenv("OBS_PORT", "4455"))
    obs_password = os.getenv("OBS_PASSWORD", "")

    client = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=5)

    if args.image_width >= 8 and args.image_height >= 8:
        shot_w, shot_h = args.image_width, args.image_height
    else:
        video = client.get_video_settings()
        base_w = getattr(video, "base_width", getattr(video, "baseWidth", 1920))
        base_h = getattr(video, "base_height", getattr(video, "baseHeight", 1080))
        shot_w = max(8, int(base_w))
        shot_h = max(8, int(base_h))

    period = 1.0 / max(1.0, args.fps)
    print(f"Debug capture: source={source_name}, screenshot={shot_w}x{shot_h}, duration={args.duration_sec}s")

    printed_shape = False
    deadline = time.time() + max(1.0, args.duration_sec)
    out_path = ROOT / "debug_last_frame.png"

    while time.time() < deadline:
        shot = client.get_source_screenshot(source_name, "png", shot_w, shot_h, 100)
        frame_bgr = decode_obs_data_url(shot.image_data)

        if not printed_shape:
            print("frame size:", frame_bgr.shape[1], "x", frame_bgr.shape[0])
            printed_shape = True

        dbg = frame_bgr.copy()
        sx, sy = int(profile["bar_start"]["x"]), int(profile["bar_start"]["y"])
        ex, ey = int(profile["bar_end"]["x"]), int(profile["bar_end"]["y"])
        cv2.circle(dbg, (sx, sy), 7, (0, 255, 0), -1)
        cv2.circle(dbg, (ex, ey), 7, (0, 0, 255), -1)
        cv2.line(dbg, (sx, sy), (ex, ey), (255, 0, 255), 2)
        cv2.imwrite(str(out_path), dbg)

        time.sleep(period)

    print(f"Wrote debug overlay: {out_path}")


if __name__ == "__main__":
    main()
