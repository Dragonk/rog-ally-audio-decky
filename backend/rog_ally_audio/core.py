from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .constants import (
    EXPECTED_AUDIO_SUBSYSTEM,
    INTERNAL_SINK_TOKEN,
    MODES,
    PROFILE_NAMES,
    SUPPORTED_MODEL_PATTERNS,
)


@dataclass(frozen=True)
class DeviceInfo:
    product_name: str = ""
    product_version: str = ""
    board_name: str = ""
    audio_subsystem: str = ""
    supported: bool = False
    support_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in MODES else "auto"


def is_internal_sink(sink: str) -> bool:
    return INTERNAL_SINK_TOKEN in (sink or "")


def classify_sink(sink: str) -> str:
    value = (sink or "").lower()
    if is_internal_sink(value):
        return "internal"
    if "bluez" in value or "bluetooth" in value:
        return "bluetooth"
    if "hdmi" in value:
        return "hdmi"
    if "usb" in value:
        return "usb"
    if not value:
        return "unknown"
    return "external"


def effective_mode_for(mode: str, sink: str) -> str:
    normalized = normalize_mode(mode)
    if not is_internal_sink(sink):
        return "bypass"
    if normalized == "auto":
        return "balanced"
    return normalized


def desired_profile_for(mode: str, sink: str) -> str:
    effective = effective_mode_for(mode, sink)
    return PROFILE_NAMES[effective]


def short_profile_name(profile: str) -> str:
    if not profile:
        return ""
    for mode, name in PROFILE_NAMES.items():
        if profile == name:
            return mode.capitalize()
    return profile


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def discover_audio_subsystem(codec_paths: Iterable[Path]) -> str:
    needle = "Subsystem Id:"
    for path in codec_paths:
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if needle in line:
                    return line.split(needle, 1)[1].strip().lower()
        except OSError:
            continue
    return ""


def evaluate_device(
    product_name: str,
    product_version: str = "",
    board_name: str = "",
    audio_subsystem: str = "",
) -> DeviceInfo:
    combined = " ".join((product_name, product_version, board_name)).upper()
    matched = next((p for p in SUPPORTED_MODEL_PATTERNS if p in combined), "")

    if matched:
        supported = True
        reason = f"matched model identifier: {matched}"
    else:
        supported = False
        reason = "RC73XA / ROG Xbox Ally X identifier not found"

    # Audio subsystem is diagnostic only for v0.1. It must not broaden the
    # supported-device set because the speaker tuning is hardware-specific.
    if audio_subsystem and audio_subsystem.lower() == EXPECTED_AUDIO_SUBSYSTEM.lower():
        reason += "; ALC294 subsystem 1043:1384 detected"

    return DeviceInfo(
        product_name=product_name,
        product_version=product_version,
        board_name=board_name,
        audio_subsystem=audio_subsystem,
        supported=supported,
        support_reason=reason,
    )


def detect_device(sys_root: Path = Path("/")) -> DeviceInfo:
    dmi = sys_root / "sys/class/dmi/id"
    product_name = _read_text(dmi / "product_name")
    product_version = _read_text(dmi / "product_version")
    board_name = _read_text(dmi / "board_name")

    codec_root = sys_root / "proc/asound"
    codec_paths = list(codec_root.glob("card*/codec#*")) if codec_root.exists() else []
    audio_subsystem = discover_audio_subsystem(codec_paths)

    return evaluate_device(
        product_name,
        product_version,
        board_name,
        audio_subsystem,
    )
