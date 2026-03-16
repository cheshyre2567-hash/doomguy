import sys
import types

import numpy as np

# Allow importing relay helpers without requiring OBS websocket runtime deps.
sys.modules.setdefault("obsws_python", types.SimpleNamespace())

from examples.obs_to_overlay_relay import resolve_hud_anchor_visible


def test_hud_anchor_single_color_match():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[5, 6] = [12, 34, 56]
    profile = {
        "hud_anchor": {
            "x": 6,
            "y": 5,
            "color_bgr": [12, 34, 56],
            "tolerance": 0,
        }
    }
    assert resolve_hud_anchor_visible(frame, profile) is True


def test_hud_anchor_multi_color_options_match_any_of_three():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[1, 2] = [90, 200, 255]
    profile = {
        "hud_anchor": {
            "x": 2,
            "y": 1,
            "color_bgr_options": [
                [255, 255, 255],
                [250, 230, 80],
                [90, 200, 255],
            ],
            "tolerance": 0,
        }
    }
    assert resolve_hud_anchor_visible(frame, profile) is True


def test_hud_anchor_multi_color_options_no_match_returns_false():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[1, 2] = [1, 2, 3]
    profile = {
        "hud_anchor": {
            "x": 2,
            "y": 1,
            "color_bgr_options": [
                [255, 255, 255],
                [250, 230, 80],
                [90, 200, 255],
            ],
            "tolerance": 0,
        }
    }
    assert resolve_hud_anchor_visible(frame, profile) is False


def test_hud_anchor_uses_at_most_first_three_color_options():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[3, 4] = [7, 8, 9]
    profile = {
        "hud_anchor": {
            "x": 4,
            "y": 3,
            "color_bgr_options": [
                [255, 255, 255],
                [250, 230, 80],
                [90, 200, 255],
                [7, 8, 9],
            ],
            "tolerance": 0,
        }
    }
    assert resolve_hud_anchor_visible(frame, profile) is False
