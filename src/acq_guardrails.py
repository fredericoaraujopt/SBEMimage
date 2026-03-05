"""Acquisition guardrails and lightweight diagnostics helpers.

These helpers are intentionally UI-agnostic so they can be used from both
manual actions (Viewport) and automated acquisition paths (Acquisition).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple


@dataclass
class GuardrailResult:
    ok: bool
    level: str
    message: str
    suggested_pixel_size: float | None = None


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def compute_magnification(sem, frame_size, pixel_size_nm: float) -> float:
    width_px = frame_size[0]
    if width_px <= 0 or pixel_size_nm <= 0:
        return 0.0
    return sem.MAG_PX_SIZE_FACTOR / (width_px * pixel_size_nm)


def recommended_ov_tile_factor(
    sem,
    frame_size,
    pixel_size_nm: float,
    min_single_frame_mag: float,
) -> int:
    mag = compute_magnification(sem, frame_size, pixel_size_nm)
    if min_single_frame_mag <= 0:
        return 1
    if mag <= 0:
        return 1
    factor = int(max(1, round(min_single_frame_mag / mag)))
    if factor * factor < (min_single_frame_mag / mag):
        factor += 1
    return max(1, factor)


def guardrail_for_grid_params(
    sem,
    frame_size,
    pixel_size_nm: float,
    min_mag: float = 60.0,
    max_mag: float = 25000.0,
) -> GuardrailResult:
    mag = compute_magnification(sem, frame_size, pixel_size_nm)
    if mag <= 0:
        return GuardrailResult(False, "error", "Invalid magnification estimate.")
    if mag < min_mag:
        suggested = sem.MAG_PX_SIZE_FACTOR / (frame_size[0] * min_mag)
        return GuardrailResult(
            False,
            "warning",
            f"Estimated magnification {mag:.1f}x is below the reliable range (< {min_mag:.0f}x).",
            suggested_pixel_size=suggested,
        )
    if mag > max_mag:
        suggested = sem.MAG_PX_SIZE_FACTOR / (frame_size[0] * max_mag)
        return GuardrailResult(
            False,
            "warning",
            f"Estimated magnification {mag:.1f}x is above the reliable range (> {max_mag:.0f}x).",
            suggested_pixel_size=suggested,
        )
    return GuardrailResult(True, "info", f"Estimated magnification: {mag:.1f}x.")


def ov_diagnostics_payload(sem, ov) -> Dict[str, Any]:
    requested_frame = list(ov.frame_size)
    requested_mag = compute_magnification(sem, requested_frame, ov.pixel_size)
    payload = {
        "requested_frame": requested_frame,
        "requested_pixel_size_nm": float(ov.pixel_size),
        "requested_mag": float(requested_mag),
        "dwell_us": float(ov.dwell_time),
        "bit_depth_selector": int(getattr(ov, "bit_depth_selector", 0)),
    }
    try:
        current_selector = sem.get_frame_size_selector()
        payload["sem_frame_selector"] = int(current_selector)
        if 0 <= current_selector < len(sem.STORE_RES):
            payload["sem_frame"] = list(sem.STORE_RES[current_selector])
    except Exception:
        payload["sem_frame_selector"] = None
    return payload


def stage_delta(commanded_xy: Tuple[float, float], actual_xy: Tuple[float, float]) -> Tuple[float, float]:
    return (actual_xy[0] - commanded_xy[0], actual_xy[1] - commanded_xy[1])
