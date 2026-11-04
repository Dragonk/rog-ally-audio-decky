from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


VIRTUAL_OUTPUT_TOKENS = ("easyeffects_sink", "easy effects sink")
VIRTUAL_INPUT_TOKENS = ("easyeffects_source", "easy effects source")


@dataclass(frozen=True)
class AudioDevice:
    name: str
    description: str
    state: str = ""
    active_port: str = ""
    default: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _blocks(text: str, header: str) -> Iterable[list[str]]:
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith(header):
            if current:
                yield current
            current = [line]
        elif current:
            current.append(line)
    if current:
        yield current


def _field(lines: Iterable[str], key: str) -> str:
    prefix = f"{key}:"
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith(prefix):
            return stripped.split(":", 1)[1].strip()
    return ""


def _is_virtual(name: str, description: str, kind: str) -> bool:
    value = f"{name} {description}".lower()
    tokens = VIRTUAL_OUTPUT_TOKENS if kind == "sink" else VIRTUAL_INPUT_TOKENS
    return any(token in value for token in tokens)


def parse_devices(text: str, kind: str, default_name: str = "") -> list[AudioDevice]:
    if kind not in {"sink", "source"}:
        raise ValueError(f"invalid audio device kind: {kind}")

    header = "Sink #" if kind == "sink" else "Source #"
    result: list[AudioDevice] = []

    for block in _blocks(text, header):
        name = _field(block, "Name")
        description = _field(block, "Description") or name
        state = _field(block, "State")
        active_port = _field(block, "Active Port")
        if not name:
            continue
        if kind == "source" and name.endswith(".monitor"):
            continue
        if _is_virtual(name, description, kind):
            continue
        result.append(
            AudioDevice(
                name=name,
                description=description,
                state=state,
                active_port=active_port,
                default=name == default_name,
            )
        )

    return result
