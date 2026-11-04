from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import decky

PLUGIN_DIR = Path(os.environ.get("DECKY_PLUGIN_DIR", Path(__file__).parent))
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from backend.rog_ally_audio.constants import MODES
from backend.rog_ally_audio.core import normalize_mode
from backend.rog_ally_audio.audio_devices import parse_devices
from backend.rog_ally_audio.runtime_manager import (
    RuntimeManager,
)


class Plugin:
    def __init__(self) -> None:
        home = Path(os.environ.get("DECKY_USER_HOME", Path.home()))
        self.runtime = RuntimeManager(PLUGIN_DIR, home)
        self.config_dir = self.runtime.config_dir
        self.mode_file = self.runtime.mode_file
        self.request_file = self.runtime.request_file
        self.status_file = self.runtime.status_file

    def _ensure_config(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.mode_file.exists():
            self._atomic_text(self.mode_file, "auto\n")

    @staticmethod
    def _atomic_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def _atomic_json(self, path: Path, data: dict[str, Any]) -> None:
        self._atomic_text(path, json.dumps(data, ensure_ascii=False))

    def _read_mode(self) -> str:
        try:
            return normalize_mode(self.mode_file.read_text(encoding="utf-8"))
        except OSError:
            return "auto"

    def _read_status(self) -> dict[str, Any]:
        try:
            value = json.loads(self.status_file.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _request(self, mode: str, action: str = "apply") -> str:
        request_id = f"{time.time_ns()}-{action}-{mode}"
        self._atomic_text(self.mode_file, mode + "\n")
        self._atomic_json(
            self.request_file,
            {
                "id": request_id,
                "mode": mode,
                "action": action,
                "created_at": time.time_ns(),
            },
        )
        return request_id

    @staticmethod
    def _request_is_audibly_ready(state: dict[str, Any]) -> bool:
        """Require proof of a live DSP path, not just a remembered preset.

        EasyEffects can remember/report a preset name while the Flatpak process
        or PipeWire graph is gone.  That was the cause of Balanced and Bypass
        sounding identical on SteamOS.
        """
        if not state.get("controller_ok"):
            return False
        if not state.get("easyeffects_server_ok"):
            return False
        if not state.get("easyeffects_service_active"):
            return False
        if not state.get("easyeffects_ok"):
            return False

        dsp = str(state.get("dsp_status") or "")
        streams = int(state.get("audio_streams") or 0)
        expected = int(state.get("dsp_effects_expected") or 0)

        if expected == 0:
            return dsp == "bypass-confirmed"
        if streams == 0:
            return dsp in {"waiting-audio", "chain-present"}
        return dsp == "chain-present"

    async def _wait_for_request(self, request_id: str, timeout: float) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        last: dict[str, Any] = {}
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.10)
            last = self._read_status()
            if last.get("applied_request_id") == request_id:
                if self._request_is_audibly_ready(last):
                    return last
                # Give the PipeWire graph a short time to instantiate after a
                # successful preset load. Do not return a false success while
                # DSP is offline/missing.
                if str(last.get("dsp_status") or "") in {
                    "ee-offline",
                    "chain-missing",
                    "partial",
                    "profile-mismatch",
                    "bypass-mismatch",
                }:
                    await asyncio.sleep(0.20)
        error = last.get("last_error")
        if not error:
            error = (
                "DSP path not confirmed: "
                f"service={last.get('easyeffects_service_active')} "
                f"server={last.get('easyeffects_server_ok')} "
                f"profile={last.get('actual_profile')!r} "
                f"dsp={last.get('dsp_status')!r} "
                f"effects={last.get('dsp_effects_present')}/{last.get('dsp_effects_expected')}"
            )
        raise RuntimeError(str(error))

    def _merged_state(self) -> dict[str, Any]:
        self._ensure_config()
        runtime_state = self.runtime.state()
        status = self._read_status()
        mode = self._read_mode()

        merged: dict[str, Any] = {
            "mode": mode,
            "setup_state": runtime_state.setup_state,
            "setup_error": runtime_state.setup_error,
            "runtime_ready": runtime_state.runtime_ready,
            "easyeffects_installed": runtime_state.easyeffects_installed,
            "easyeffects_service_active": runtime_state.easyeffects_service_active,
            "controller_service_active": runtime_state.controller_service_active,
            "gui_active": runtime_state.gui_active,
            "device": runtime_state.device.to_dict(),
        }
        merged.update(status)
        # The persisted user choice is authoritative; controller status can be
        # stale during startup and must not replace it.
        merged["mode"] = mode
        return merged

    async def get_state(self) -> dict[str, Any]:
        return self._merged_state()

    def _audio_devices(self, kind: str) -> list[dict[str, Any]]:
        if kind not in {"sink", "source"}:
            raise ValueError(f"Invalid audio device kind: {kind}")
        noun = "sinks" if kind == "sink" else "sources"
        default_cmd = "get-default-sink" if kind == "sink" else "get-default-source"
        default_result = self.runtime.runner.run(["/usr/bin/pactl", default_cmd], timeout=3)
        default_name = default_result.stdout.strip() if default_result.returncode == 0 else ""
        listing = self.runtime.runner.run(["/usr/bin/pactl", "list", noun], timeout=5)
        if listing.returncode != 0:
            raise RuntimeError(listing.stderr.strip() or f"Could not list {noun}")
        return [item.to_dict() for item in parse_devices(listing.stdout, kind, default_name)]

    async def list_audio_devices(self) -> dict[str, Any]:
        return {
            "outputs": self._audio_devices("sink"),
            "inputs": self._audio_devices("source"),
        }

    async def set_output_device(self, name: str) -> dict[str, Any]:
        available = {str(item["name"]) for item in self._audio_devices("sink")}
        if name not in available:
            raise ValueError("Unknown or virtual output device")
        result = self.runtime.runner.run(
            ["/usr/bin/pactl", "set-default-sink", name], timeout=4
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Could not change output device")
        # Force the controller to immediately re-evaluate routing and move
        # already-running playback streams to the new physical destination.
        mode = self._read_mode()
        request_id = self._request(mode, "apply")
        await self._wait_for_request(request_id, 5.5)
        return self._merged_state()

    async def set_input_device(self, name: str) -> dict[str, Any]:
        available = {str(item["name"]) for item in self._audio_devices("source")}
        if name not in available:
            raise ValueError("Unknown or virtual input device")
        result = self.runtime.runner.run(
            ["/usr/bin/pactl", "set-default-source", name], timeout=4
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Could not change input device")
        await asyncio.sleep(0.25)
        return self._merged_state()

    async def set_mode(self, mode: str) -> dict[str, Any]:
        raw = str(mode or "").strip().lower()
        if raw not in MODES:
            raise ValueError(f"Invalid mode: {mode}")
        normalized = raw
        if not self.runtime.state().runtime_ready:
            raise RuntimeError("ROG Ally Audio runtime is not ready")

        request_id = self._request(normalized, "apply")
        await self._wait_for_request(request_id, 5.5)
        return self._merged_state()

    async def reapply(self) -> dict[str, Any]:
        if not self.runtime.state().runtime_ready:
            raise RuntimeError("ROG Ally Audio runtime is not ready")
        mode = self._read_mode()
        request_id = self._request(mode, "apply")
        await self._wait_for_request(request_id, 5.5)
        return self._merged_state()

    async def ab_test(self) -> dict[str, Any]:
        state = self._merged_state()
        if not state.get("internal_active", False):
            raise RuntimeError("A/B test is available only on built-in speakers")
        mode = self._read_mode()
        request_id = self._request(mode, "ab_test")
        await self._wait_for_request(request_id, 7.5)
        return self._merged_state()

    async def repair_setup(self) -> dict[str, Any]:
        await asyncio.to_thread(self.runtime.bootstrap, force=True)
        return self._merged_state()

    async def install_easyeffects(self) -> dict[str, Any]:
        await asyncio.to_thread(self.runtime.install_easyeffects)
        await asyncio.to_thread(self.runtime.bootstrap, force=True)
        return self._merged_state()

    async def reset_factory_presets(self) -> dict[str, Any]:
        await asyncio.to_thread(
            self.runtime.bootstrap,
            force=True,
            force_presets=True,
        )
        return self._merged_state()

    async def _main(self) -> None:
        self._ensure_config()
        state = self.runtime.state()
        if state.device.supported and state.easyeffects_installed:
            try:
                await asyncio.to_thread(self.runtime.bootstrap)
            except Exception:
                decky.logger.exception("ROG Ally Audio automatic bootstrap failed")
        elif not state.device.supported:
            decky.logger.warning(
                "ROG Ally Audio: unsupported device: %s",
                state.device.support_reason,
            )
        else:
            decky.logger.info("ROG Ally Audio: EasyEffects is not installed yet")

    async def _unload(self) -> None:
        # Services intentionally remain active when Decky reloads the plugin.
        decky.logger.info("ROG Ally Audio plugin unloaded; audio runtime left running")

    async def _uninstall(self) -> None:
        await asyncio.to_thread(self.runtime.uninstall_runtime)
        decky.logger.info(
            "ROG Ally Audio runtime removed; EasyEffects, presets and user settings preserved"
        )
