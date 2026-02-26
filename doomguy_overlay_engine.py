"""Core state engine for selecting Doomguy face frames from health + damage signals.

This module is intentionally framework-agnostic so it can be reused by any relay
(server, OBS script, websocket worker, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LookDirection = Literal["left", "center", "right"]


@dataclass(frozen=True)
class FaceState:
    """Resolved frame names for the current tick."""

    look: LookDirection
    health_percent: int
    health_bucket: int
    frame_name: str
    is_pain: bool


class DoomguyFaceEngine:
    """State machine for health-based Doomguy face animation.

    - Cycles look direction in this order: center -> left -> center -> right -> ...
    - Uses STFSTxx frame sets for health buckets.
    - Uses STFOUCHx for damage pulses based on current health bucket.
    """

    _LOOK_SEQUENCE: tuple[LookDirection, ...] = ("center", "left", "center", "right")
    _LOOK_TO_INDEX: dict[LookDirection, int] = {"left": 0, "center": 1, "right": 2}

    def __init__(self) -> None:
        self._look_cursor = 0
        self._pain_ticks_remaining = 0
        self._last_health = 100

    @staticmethod
    def health_to_bucket(health_percent: int) -> int:
        """Map health percent to Doomguy's 5 face health buckets.

        Buckets:
        - 0 => 80-100
        - 1 => 60-79
        - 2 => 40-59
        - 3 => 20-39
        - 4 => 1-19

        If health <= 0, callers should typically use STFDEAD0 externally.
        """

        h = max(0, min(100, int(health_percent)))
        if h >= 80:
            return 0
        if h >= 60:
            return 1
        if h >= 40:
            return 2
        if h >= 20:
            return 3
        return 4

    def notify_damage(self, amount: int = 1, pain_ticks: int = 3) -> None:
        """Trigger a pain animation pulse.

        amount is currently only semantic (future expansion). pain_ticks controls how
        many update ticks STFOUCHx should remain active.
        """

        if amount > 0:
            self._pain_ticks_remaining = max(self._pain_ticks_remaining, pain_ticks)

    def update(self, health_percent: int) -> FaceState:
        """Advance animation and return the active frame for this tick."""

        h = max(0, min(100, int(health_percent)))

        if h < self._last_health:
            self.notify_damage(self._last_health - h)
        self._last_health = h

        look = self._LOOK_SEQUENCE[self._look_cursor]
        self._look_cursor = (self._look_cursor + 1) % len(self._LOOK_SEQUENCE)

        look_index = self._LOOK_TO_INDEX[look]
        bucket = self.health_to_bucket(h)

        if h <= 0:
            return FaceState(
                look=look,
                health_percent=h,
                health_bucket=4,
                frame_name="STFDEAD0",
                is_pain=False,
            )

        if self._pain_ticks_remaining > 0:
            self._pain_ticks_remaining -= 1
            return FaceState(
                look=look,
                health_percent=h,
                health_bucket=bucket,
                frame_name=f"STFOUCH{bucket}",
                is_pain=True,
            )

        return FaceState(
            look=look,
            health_percent=h,
            health_bucket=bucket,
            frame_name=f"STFST{bucket}{look_index}",
            is_pain=False,
        )
