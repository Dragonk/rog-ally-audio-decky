#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config" / "rog-ally-audio"
MODE_FILE = CONFIG / "mode"
REQUEST_FILE = CONFIG / "request.json"
STATUS_FILE = CONFIG / "status.json"
ROUTING_STATE_FILE = CONFIG / "routing.json"

APP_ID = "com.github.wwmm.easyeffects"
EE_SERVICE = "decky-rog-ally-audio-easyeffects.service"
KDE_EE_SERVICE = "decky-rog-ally-audio-easyeffects-kde.service"
SESSION_SERVICE = "decky-rog-ally-audio-session.service"
SESSION_FILE = CONFIG / "session.json"
INTERNAL_TOKEN = "pci-0000_64_00.6.analog-stereo"

PROFILES = {
    "balanced": "ROG Xbox Ally X - Experimental Balanced",
    "cinema": "ROG Xbox Ally X - Experimental Cinema",
    "loud": "ROG Xbox Ally X - Experimental Loud",
    "bypass": "ROG Xbox Ally X - Bypass",
}
VALID = {"auto", "balanced", "cinema", "loud", "bypass"}
PROFILE_TO_MODE = {value: key for key, value in PROFILES.items()}

RUNTIME = f"/run/user/{os.getuid()}"
CLEAN_ENV = {
    "HOME": str(HOME),
    "USER": os.environ.get("USER", HOME.name),
    "LOGNAME": os.environ.get("LOGNAME", HOME.name),
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin:/bin",
    "XDG_RUNTIME_DIR": RUNTIME,
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path={RUNTIME}/bus",
    "LANG": "C.UTF-8",
}

EE_HELPER = r'''
import socket
import sys
import time

operation = sys.argv[1]
value = sys.argv[2] if len(sys.argv) > 2 else ""

def send(command, reply=False):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect("/tmp/EasyEffectsServer")
    s.sendall((command + "\n").encode("utf-8"))
    out = ""
    if reply:
        try:
            out = s.recv(4096).decode(errors="replace").strip()
        except socket.timeout:
            pass
    s.close()
    return out

if operation == "get":
    print(send("get_last_loaded_preset:output", True))
    raise SystemExit(0)

if operation == "load":
    send("global_bypass:0")
    send("load_preset:output:" + value)
    time.sleep(0.30)
    actual = send("get_last_loaded_preset:output", True)
    print(actual)
    raise SystemExit(0 if actual == value else 2)

raise SystemExit(3)
'''

DSP_TOKENS = {
    "filter": "ee_soe_filter",
    "bass": "bass_enhancer",
    "compressor": "multiband_compressor",
    "stereo": "stereo_tools",
    "limiter": "ee_soe_limiter",
}


def run(cmd: list[str], timeout: float = 4) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=CLEAN_ENV,
    )


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, value: dict) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False))


def normalize_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in VALID else "auto"


def read_mode() -> str:
    try:
        return normalize_mode(MODE_FILE.read_text(encoding="utf-8"))
    except OSError:
        return "auto"


def read_request() -> dict[str, str]:
    try:
        data = json.loads(REQUEST_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return {
            "id": str(data.get("id", "")),
            "mode": normalize_mode(data.get("mode", read_mode())),
            "action": str(data.get("action", "apply")).strip().lower(),
        }
    except (OSError, json.JSONDecodeError, ValueError):
        return {"id": "", "mode": read_mode(), "action": "apply"}


def pactl_value(command: list[str]) -> str:
    try:
        result = run(command, 2)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_default_sink() -> str:
    return pactl_value(["/usr/bin/pactl", "get-default-sink"])


def get_default_source() -> str:
    return pactl_value(["/usr/bin/pactl", "get-default-source"])


def _blocks(text: str, header: str) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    for raw in text.splitlines():
        if raw.startswith(header):
            if current:
                result.append(current)
            current = [raw]
        elif current:
            current.append(raw)
    if current:
        result.append(current)
    return result


def _field(lines: list[str], key: str) -> str:
    prefix = f"{key}:"
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith(prefix):
            return stripped.split(":", 1)[1].strip()
    return ""


def list_sinks() -> list[dict[str, str]]:
    text = pactl_value(["/usr/bin/pactl", "list", "sinks"])
    items: list[dict[str, str]] = []
    for block in _blocks(text, "Sink #"):
        name = _field(block, "Name")
        if not name:
            continue
        items.append({
            "id": block[0].split("#", 1)[1].strip(),
            "name": name,
            "description": _field(block, "Description") or name,
            "state": _field(block, "State"),
            "active_port": _field(block, "Active Port"),
        })
    return items


def list_sources() -> list[dict[str, str]]:
    text = pactl_value(["/usr/bin/pactl", "list", "sources"])
    items: list[dict[str, str]] = []
    for block in _blocks(text, "Source #"):
        name = _field(block, "Name")
        if not name:
            continue
        items.append({
            "id": block[0].split("#", 1)[1].strip(),
            "name": name,
            "description": _field(block, "Description") or name,
            "state": _field(block, "State"),
            "active_port": _field(block, "Active Port"),
        })
    return items


def easyeffects_sink(sinks: list[dict[str, str]]) -> dict[str, str] | None:
    for sink in sinks:
        value = f"{sink['name']} {sink['description']}".lower()
        if "easyeffects_sink" in value or "easy effects sink" in value:
            return sink
    return None


def easyeffects_source(sources: list[dict[str, str]]) -> dict[str, str] | None:
    for source in sources:
        value = f"{source['name']} {source['description']}".lower()
        if "easyeffects_source" in value or "easy effects source" in value:
            return source
    return None


def active_port_for(sink_name: str, sinks: list[dict[str, str]]) -> str:
    for sink in sinks:
        if sink["name"] == sink_name:
            return sink.get("active_port", "")
    return ""


def is_internal_speaker(sink_name: str, active_port: str = "") -> bool:
    if INTERNAL_TOKEN not in (sink_name or ""):
        return False
    port = (active_port or "").lower()
    # The 3.5 mm jack is on the same ALC294 sink. Speaker tuning must never be
    # applied to headphones just because the sink name is identical.
    if "headphone" in port or "headset" in port:
        return False
    return True


def desired_for(mode: str, sink: str, active_port: str = "") -> tuple[str, str, bool]:
    internal = is_internal_speaker(sink, active_port)
    if not internal:
        return "bypass", PROFILES["bypass"], False
    if normalize_mode(mode) == "auto":
        return "balanced", PROFILES["balanced"], True
    normalized = normalize_mode(mode)
    return normalized, PROFILES[normalized], True


def should_use_easyeffects(internal: bool, desired_profile: str) -> bool:
    """Use EasyEffects for every built-in-speaker profile, including Bypass.

    Bypass means an empty effects chain, not a different audio transport.  This
    deliberately matches the original known-good routing on the Ally: while
    using the built-in speakers EasyEffects owns player redirection, and profile
    changes only swap the DSP graph.  External devices are the only case where
    routing is fully direct.
    """
    return bool(internal)


def manual_mode_override(
    actual_profile: str,
    desired_profile: str,
    *,
    internal: bool,
) -> str:
    """Return a mode selected manually in the EasyEffects GUI.

    On built-in speakers the EasyEffects preset selector is treated as a
    legitimate second UI for ROG Ally Audio. This is especially important in
    KDE, where Decky's QAM is not available. External outputs are always
    direct/bypass and must not change the persisted mode merely because the
    EasyEffects window was opened.
    """
    if not internal or not actual_profile or actual_profile == desired_profile:
        return ""
    return PROFILE_TO_MODE.get(actual_profile, "")


def _unit_active(name: str) -> bool:
    try:
        result = run(
            ["/usr/bin/systemctl", "--user", "is-active", "--quiet", name],
            2,
        )
        return result.returncode == 0
    except Exception:
        return False


def desktop_session_mode() -> str:
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        mode = str(data.get("mode", "")).strip().lower()
        if mode in {"kde", "gaming"}:
            return mode
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    try:
        result = run(["/usr/bin/pgrep", "-u", str(os.getuid()), "-x", "plasmashell"], 2)
        return "kde" if result.returncode == 0 and result.stdout.strip() else "gaming"
    except Exception:
        return "gaming"


def active_easyeffects_runtime() -> str:
    if _unit_active(KDE_EE_SERVICE):
        return "kde"
    if _unit_active(EE_SERVICE):
        return "headless"
    return ""


def service_active() -> bool:
    return bool(active_easyeffects_runtime())


def ensure_service() -> bool:
    if service_active():
        return True
    target = KDE_EE_SERVICE if desktop_session_mode() == "kde" else EE_SERVICE
    try:
        # Ask the session manager to converge first; fall back to the correct
        # owner service only if it has not reacted yet. Never start the
        # offscreen instance in Plasma because it would steal the single
        # EasyEffects application instance and make the tray/window impossible.
        run(["/usr/bin/systemctl", "--user", "start", SESSION_SERVICE], 6)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if service_active():
                return True
            time.sleep(0.20)
        run(["/usr/bin/systemctl", "--user", "restart", target], 10)
    except Exception:
        return False
    deadline = time.monotonic() + 7
    while time.monotonic() < deadline:
        if service_active():
            return True
        time.sleep(0.25)
    return False


def configure_easyeffects_preferences(process_all_outputs: bool) -> str:
    """Set EasyEffects automatic output ownership for the current route.

    Built-in speakers: ON.  Balanced/Cinema/Loud/Bypass all stay on the same
    EasyEffects transport; only the loaded preset changes the DSP chain.

    HDMI/USB/Bluetooth/headphones: OFF.  The user's physical device selection
    stays authoritative and the plugin does not process microphone streams.

    EasyEffects' GSettings backend is dconf, so writing the user's dconf keys
    is enough and avoids spawning gsettings inside the Flatpak sandbox.
    """
    desired = "true" if process_all_outputs else "false"
    settings = {
        "process-all-outputs": desired,
        "process-all-inputs": "false",
    }
    errors: list[str] = []
    for key, value in settings.items():
        path = f"/com/github/wwmm/easyeffects/{key}"
        try:
            result = run(["/usr/bin/dconf", "write", path, value], 4)
            if result.returncode != 0:
                errors.append(result.stderr.strip() or f"dconf write {key} failed")
                continue
            verify = run(["/usr/bin/dconf", "read", path], 4)
            current = verify.stdout.strip().lower()
            if verify.returncode != 0 or current != value:
                detail = verify.stderr.strip() or current or "empty value"
                errors.append(f"dconf verify {key} failed: {detail}")
        except Exception as exc:
            errors.append(f"{key}: {exc}")
    return "; ".join(error for error in errors if error)

def ee_command(operation: str, value: str = "") -> tuple[bool, str, str]:
    if not ensure_service():
        return False, "", "persistent EasyEffects service is inactive"
    try:
        result = run(
            [
                "/usr/bin/flatpak", "enter", APP_ID,
                "python3", "-c", EE_HELPER, operation, value,
            ],
            7,
        )
    except Exception as exc:
        return False, "", repr(exc)

    stdout = result.stdout.strip()
    ok = result.returncode == 0 and (bool(stdout) if operation == "get" else stdout == value)
    detail = "" if ok else (result.stderr.strip() or stdout or f"exit={result.returncode}")
    return ok, stdout, detail


def load_profile(preset: str) -> tuple[bool, str, str]:
    return ee_command("load", preset)


def read_actual_profile() -> tuple[bool, str, str]:
    return ee_command("get", "")


def parse_sink_inputs(text: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for block in _blocks(text, "Sink Input #"):
        index = block[0].split("#", 1)[1].strip()
        sink_id = _field(block, "Sink")
        props: dict[str, str] = {}
        in_props = False
        for raw in block:
            stripped = raw.strip()
            if stripped == "Properties:":
                in_props = True
                continue
            if in_props:
                match = re.match(r'([^=]+)=\s*"?(.*?)"?$', stripped)
                if match:
                    props[match.group(1).strip()] = match.group(2).strip().strip('"')
        result.append({"index": index, "sink_id": sink_id, "properties": props})
    return result


def is_easyeffects_stream(stream: dict[str, object]) -> bool:
    props = stream.get("properties", {})
    if not isinstance(props, dict):
        return False
    value = " ".join(str(v) for v in props.values()).lower()
    return "easy effects" in value or "easyeffects" in value or APP_ID.lower() in value


def move_sink_input(index: str, target: str) -> bool:
    try:
        result = run(["/usr/bin/pactl", "move-sink-input", str(index), target], 3)
        return result.returncode == 0
    except Exception:
        return False


def route_streams(
    physical_sink: str,
    use_easyeffects: bool,
    sinks: list[dict[str, str]],
    *,
    force_all: bool,
    seen_streams: set[str],
) -> tuple[int, set[str], str]:
    ee_sink = easyeffects_sink(sinks)
    if not ee_sink:
        return 0, seen_streams, "Easy Effects Sink not found"

    sink_id_to_name = {item["id"]: item["name"] for item in sinks}
    text = pactl_value(["/usr/bin/pactl", "list", "sink-inputs"])
    streams = parse_sink_inputs(text)
    moved = 0
    current_ids: set[str] = set()

    for stream in streams:
        index = str(stream["index"])
        current_ids.add(index)
        current_sink = sink_id_to_name.get(str(stream.get("sink_id", "")), "")

        if is_easyeffects_stream(stream):
            # EasyEffects' own playback stream must always terminate at the
            # selected physical output, otherwise the virtual sink can form a
            # loop or keep playing through a previously selected dock.
            if physical_sink and current_sink != physical_sink:
                moved += int(move_sink_input(index, physical_sink))
            continue

        is_new = index not in seen_streams
        if not (force_all or is_new):
            continue

        target = ee_sink["name"] if use_easyeffects else physical_sink
        if target and current_sink != target:
            moved += int(move_sink_input(index, target))

    return moved, current_ids, ""


def audio_stream_count() -> int:
    try:
        text = pactl_value(["/usr/bin/pactl", "list", "sink-inputs"])
        return sum(1 for stream in parse_sink_inputs(text) if not is_easyeffects_stream(stream))
    except Exception:
        return 0


def dsp_snapshot(
    desired_profile: str,
    actual_profile: str,
    ee_ok: bool,
    streams: int,
    graph: str | None = None,
) -> tuple[str, int, int]:
    if not ee_ok:
        return "ee-offline", 0, 5

    if graph is None:
        try:
            graph = run(["/usr/bin/pw-link", "-l"], 2).stdout.lower()
        except Exception:
            return "unknown", 0, 5
    else:
        graph = graph.lower()

    present = sum(1 for token in DSP_TOKENS.values() if token.lower() in graph)
    bypass_requested = desired_profile == PROFILES["bypass"]
    bypass_actual = actual_profile == PROFILES["bypass"]

    if bypass_requested:
        if not bypass_actual:
            return "bypass-mismatch", present, 0
        if present == 0:
            return "bypass-confirmed", 0, 0
        return "bypass-mismatch", present, 0

    if actual_profile != desired_profile:
        return "profile-mismatch", present, 5
    if present == 5:
        return "chain-present", 5, 5
    if present > 0:
        return "partial", present, 5
    if streams == 0:
        return "waiting-audio", 0, 5
    return "chain-missing", 0, 5


def dsp_requires_self_heal(
    internal: bool,
    desired_profile: str,
    streams: int,
    dsp_status: str,
) -> bool:
    """Return True only for a broken *live* built-in-speaker DSP path.

    PipeWire is allowed to remove the whole graph while idle.  Self-healing
    therefore starts only after a real application stream exists.
    """
    if not internal or streams <= 0:
        return False
    if desired_profile == PROFILES["bypass"]:
        return dsp_status != "bypass-confirmed"
    return dsp_status != "chain-present"


def write_status(state: dict) -> None:
    state["updated_at"] = int(time.time())
    atomic_json(STATUS_FILE, state)


def main() -> int:
    CONFIG.mkdir(parents=True, exist_ok=True)
    if not MODE_FILE.exists():
        atomic_text(MODE_FILE, "auto\n")

    pref_error = ""
    current_actual = ""
    last_error = pref_error
    server_ok = False
    profile_ok = False
    last_applied_route: tuple[str, str, str, str] | None = None
    last_explicit_request = ""
    applied_request_id = ""
    retry_at = 0.0
    retry_pending = False
    last_actual_probe = 0.0
    last_dsp_probe = 0.0
    last_pref_probe = time.monotonic()
    dsp_status = "unknown"
    dsp_present = 0
    dsp_expected = 5
    streams = 0
    test_phase = ""
    seen_streams: set[str] = set()
    last_physical_sink = ""
    dsp_bad_since = 0.0
    last_self_heal = 0.0
    self_heal_count = 0
    last_self_heal_result = ""

    while True:
        now = time.monotonic()
        mode = read_mode()
        request = read_request()
        request_id = request["id"]
        action = request.get("action", "apply")

        sinks = list_sinks()
        sources = list_sources()
        ee_sink = easyeffects_sink(sinks)
        raw_default_sink = get_default_sink()
        default_source = get_default_source()

        # EasyEffects itself must never become the physical system default.
        if ee_sink and raw_default_sink == ee_sink["name"]:
            candidates = [s for s in sinks if s["name"] != ee_sink["name"]]
            preferred = next((s for s in candidates if s["name"] == last_physical_sink), None)
            if preferred is None:
                preferred = next((s for s in candidates if INTERNAL_TOKEN in s["name"]), None)
            if preferred is None and candidates:
                preferred = candidates[0]
            if preferred:
                run(["/usr/bin/pactl", "set-default-sink", preferred["name"]], 3)
                raw_default_sink = preferred["name"]

        physical_sink = raw_default_sink
        if physical_sink:
            last_physical_sink = physical_sink
        active_port = active_port_for(physical_sink, sinks)
        effective_mode, desired, internal = desired_for(mode, physical_sink, active_port)
        use_easyeffects = should_use_easyeffects(internal, desired)

        explicit_new = bool(request_id) and request_id != last_explicit_request
        route_key = (mode, physical_sink, active_port, desired)
        route_changed = route_key != last_applied_route

        if route_changed:
            new_pref_error = configure_easyeffects_preferences(internal)
            if new_pref_error:
                last_error = new_pref_error
            last_pref_probe = now

        if now - last_pref_probe >= 30:
            new_pref_error = configure_easyeffects_preferences(internal)
            if new_pref_error:
                last_error = new_pref_error
            last_pref_probe = now

        if explicit_new and action == "ab_test":
            last_explicit_request = request_id
            if not internal:
                profile_ok = False
                last_error = "A/B test is only available on built-in speakers"
                applied_request_id = ""
            else:
                test_phase = "bypass"
                ok1, actual1, err1 = load_profile(PROFILES["bypass"])
                if ok1:
                    current_actual = actual1
                    _, seen_streams, _ = route_streams(
                        physical_sink, True, sinks,
                        force_all=True, seen_streams=seen_streams,
                    )
                    time.sleep(2.0)
                    test_phase = "restore"
                    ok2, actual2, err2 = load_profile(desired)
                    if ok2:
                        current_actual = actual2
                        _, seen_streams, _ = route_streams(
                            physical_sink,
                            should_use_easyeffects(internal, desired),
                            sinks, force_all=True, seen_streams=seen_streams,
                        )
                        profile_ok = True
                        server_ok = True
                        last_error = ""
                        applied_request_id = request_id
                        last_applied_route = route_key
                    else:
                        profile_ok = False
                        server_ok = False
                        last_error = err2
                else:
                    profile_ok = False
                    server_ok = False
                    last_error = err1
            test_phase = ""

        elif explicit_new or route_changed or (retry_pending and now >= retry_at):
            if explicit_new:
                last_explicit_request = request_id
            ok, actual, error = load_profile(desired)
            if ok:
                server_ok = True
                current_actual = actual
                profile_ok = True
                retry_pending = False
                last_error = ""
                if explicit_new:
                    applied_request_id = request_id
            else:
                server_ok = False
                current_actual = ""
                profile_ok = False
                retry_pending = True
                last_error = error
                retry_at = now + 1.0

        # Route existing streams on a physical output/port/profile change. New
        # streams are routed as they appear, without continuously fighting
        # later per-application choices made by the user.
        moved, seen_now, routing_error = route_streams(
            physical_sink,
            use_easyeffects,
            sinks,
            force_all=route_changed,
            seen_streams=seen_streams,
        )
        seen_streams = seen_now
        if routing_error:
            last_error = routing_error
        if route_changed and not routing_error:
            last_applied_route = route_key

        if now - last_actual_probe >= 0.5:
            probe_ok, probe_actual, probe_error = read_actual_profile()
            server_ok = probe_ok
            if probe_ok:
                current_actual = probe_actual

                # KDE users can select one of our four factory profiles
                # directly in EasyEffects. Treat that as a user action instead
                # of immediately overwriting it with the Decky-selected mode.
                manual_mode = manual_mode_override(
                    current_actual, desired, internal=internal
                )
                if manual_mode:
                    atomic_text(MODE_FILE, manual_mode + "\n")
                    mode = manual_mode
                    effective_mode, desired, internal = desired_for(
                        mode, physical_sink, active_port
                    )
                    use_easyeffects = should_use_easyeffects(internal, desired)
                    route_key = (mode, physical_sink, active_port, desired)
                    _, seen_streams, manual_routing_error = route_streams(
                        physical_sink,
                        use_easyeffects,
                        sinks,
                        force_all=True,
                        seen_streams=seen_streams,
                    )
                    if not manual_routing_error:
                        last_applied_route = route_key
                        routing_error = ""
                    else:
                        routing_error = manual_routing_error
                    profile_ok = current_actual == desired
                    retry_pending = False
                    last_error = routing_error
                else:
                    profile_ok = current_actual == desired
                    # A known, manually selected profile mismatch is not a
                    # transient failure. Never fight the EasyEffects GUI.
                    if current_actual in PROFILE_TO_MODE:
                        retry_pending = False
                    if profile_ok and not routing_error:
                        last_error = ""
            else:
                current_actual = ""
                profile_ok = False
                retry_pending = True
                retry_at = now + 1.0
                last_error = probe_error
            last_actual_probe = now

        if now - last_dsp_probe >= 0.75:
            streams = audio_stream_count()
            dsp_status, dsp_present, dsp_expected = dsp_snapshot(
                desired, current_actual, server_ok, streams
            )
            last_dsp_probe = now

            # Real audio is the authoritative health signal. PipeWire may tear
            # the effect graph down completely while idle, so waiting-audio is
            # normal. But once an application is playing on the built-in
            # speakers, Balanced/Cinema/Loud must expose the full 5-node graph
            # and Bypass must expose 0/0. If that contract is broken for more
            # than two seconds, repair routing/profile automatically.
            bad_live_dsp = dsp_requires_self_heal(
                internal, desired, streams, dsp_status
            )

            if bad_live_dsp:
                if dsp_bad_since == 0.0:
                    dsp_bad_since = now
                if now - dsp_bad_since >= 2.0 and now - last_self_heal >= 15.0:
                    self_heal_count += 1
                    last_self_heal = now
                    errors: list[str] = []

                    pref_issue = configure_easyeffects_preferences(True)
                    if pref_issue:
                        errors.append(pref_issue)

                    # Reloading the selected factory profile recreates the DSP
                    # chain without changing the user's mode. ee_command also
                    # restarts the persistent service if it disappeared.
                    heal_ok, heal_actual, heal_error = load_profile(desired)
                    if heal_ok:
                        server_ok = True
                        current_actual = heal_actual
                        profile_ok = heal_actual == desired
                    else:
                        errors.append(heal_error or "profile reload failed")

                    # Force every existing player through the expected route.
                    # New streams remain handled by normal stream discovery.
                    sinks = list_sinks()
                    moved_heal, seen_streams, heal_route_error = route_streams(
                        physical_sink,
                        should_use_easyeffects(internal, desired),
                        sinks,
                        force_all=True,
                        seen_streams=seen_streams,
                    )
                    moved += moved_heal
                    if heal_route_error:
                        errors.append(heal_route_error)

                    last_self_heal_result = "ok" if not errors else "; ".join(errors)
                    if errors:
                        last_error = "DSP self-heal: " + last_self_heal_result
                    else:
                        last_error = ""
                    dsp_bad_since = 0.0
            else:
                dsp_bad_since = 0.0

        write_status({
            "mode": mode,
            "effective_mode": effective_mode,
            "effective_profile": desired,
            "actual_profile": current_actual,
            "default_sink": physical_sink,
            "default_source": default_source,
            "active_output_port": active_port,
            "internal_active": internal,
            "controller_ok": True,
            "easyeffects_ok": profile_ok,
            "easyeffects_server_ok": server_ok,
            "easyeffects_service_active": service_active(),
            "easyeffects_runtime": active_easyeffects_runtime(),
            "desktop_session_mode": desktop_session_mode(),
            "request_id": request_id,
            "applied_request_id": applied_request_id,
            "last_action_result": "loaded" if profile_ok else "load_failed",
            "last_error": last_error,
            "dsp_status": dsp_status,
            "dsp_effects_present": dsp_present,
            "dsp_effects_expected": dsp_expected,
            "audio_streams": streams,
            "streams_moved_last_cycle": moved,
            "routing_mode": "easyeffects" if use_easyeffects else "direct",
            "test_phase": test_phase,
            "self_heal_count": self_heal_count,
            "last_self_heal_result": last_self_heal_result,
        })
        time.sleep(0.25)


if __name__ == "__main__":
    while True:
        try:
            raise SystemExit(main())
        except KeyboardInterrupt:
            raise SystemExit(0)
        except SystemExit:
            raise
        except Exception as exc:
            try:
                write_status({
                    "controller_ok": False,
                    "easyeffects_ok": False,
                    "last_action_result": "controller_exception",
                    "last_error": repr(exc),
                })
            except Exception:
                pass
            time.sleep(1.0)
