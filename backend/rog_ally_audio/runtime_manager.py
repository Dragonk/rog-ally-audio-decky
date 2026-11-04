from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .constants import (
    APP_ID,
    CONFIG_DIRNAME,
    CONTROLLER_SERVICE,
    DATA_DIRNAME,
    EE_SERVICE,
    KDE_EE_SERVICE,
    SESSION_SERVICE,
    LEGACY_CONFIG_DIRNAME,
    LEGACY_CONTROLLER_SERVICE,
    LEGACY_EE_SERVICE,
    PLUGIN_VERSION,
)
from .core import DeviceInfo, detect_device, normalize_mode
from .presets import PresetManager


class RuntimeSetupError(RuntimeError):
    pass


class MissingDependencyError(RuntimeSetupError):
    pass


class UnsupportedDeviceError(RuntimeSetupError):
    pass


@dataclass
class RuntimeState:
    device: DeviceInfo
    easyeffects_installed: bool
    easyeffects_service_active: bool
    controller_service_active: bool
    gui_active: bool
    runtime_ready: bool
    setup_state: str
    setup_error: str = ""

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["device"] = self.device.to_dict()
        return result


class CommandRunner:
    def __init__(self, home: Path, uid: int | None = None):
        self.home = Path(home)
        self.uid = os.getuid() if uid is None else uid

    def clean_env(self) -> dict[str, str]:
        runtime = f"/run/user/{self.uid}"
        # Intentionally do not inherit Decky/PyInstaller LD_* variables. This
        # mirrors the successful AutoFlatpaks pattern and prevents system
        # flatpak from loading Decky's bundled OpenSSL libraries.
        return {
            "HOME": str(self.home),
            "USER": self.home.name,
            "LOGNAME": self.home.name,
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin:/bin",
            "XDG_RUNTIME_DIR": runtime,
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus",
            "LANG": "C.UTF-8",
        }

    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float = 15,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=check,
            env=self.clean_env(),
        )


class RuntimeManager:
    def __init__(
        self,
        plugin_dir: Path,
        home: Path,
        *,
        runner: CommandRunner | None = None,
    ):
        self.plugin_dir = Path(plugin_dir)
        self.home = Path(home)
        self.runner = runner or CommandRunner(self.home)

        self.config_dir = self.home / ".config" / CONFIG_DIRNAME
        self.data_dir = self.home / ".local/share" / DATA_DIRNAME
        self.unit_dir = self.home / ".config/systemd/user"
        self.controller_target = self.data_dir / "controller.py"
        self.session_manager_target = self.data_dir / "session_manager.py"
        self.kde_launcher_target = self.data_dir / "easyeffects-kde.sh"
        self.gui_wrapper_target = self.data_dir / "easyeffects-gui-wrapper.sh"
        self.desktop_entry_target = self.home / ".local/share/applications/rog-ally-audio-easyeffects.desktop"
        self.legacy_desktop_entry_target = self.home / ".local/share/applications/com.github.wwmm.easyeffects.desktop"
        self.mode_file = self.config_dir / "mode"
        self.request_file = self.config_dir / "request.json"
        self.status_file = self.config_dir / "status.json"
        self.gui_active_file = self.config_dir / "gui-active"  # legacy sentinel
        self.session_state_file = self.config_dir / "session.json"
        self.setup_error_file = self.data_dir / "setup-error.txt"
        self.install_manifest = self.data_dir / "install.json"

        self.preset_manager = PresetManager(
            self.plugin_dir,
            self.home,
            self.data_dir,
        )

    @property
    def ee_unit_path(self) -> Path:
        return self.unit_dir / EE_SERVICE

    @property
    def kde_ee_unit_path(self) -> Path:
        return self.unit_dir / KDE_EE_SERVICE

    @property
    def session_unit_path(self) -> Path:
        return self.unit_dir / SESSION_SERVICE

    @property
    def controller_unit_path(self) -> Path:
        return self.unit_dir / CONTROLLER_SERVICE

    def _systemctl(self, *args: str, timeout: float = 12):
        return self.runner.run(
            ["/usr/bin/systemctl", "--user", *args], timeout=timeout
        )

    def _service_active(self, name: str) -> bool:
        try:
            result = self._systemctl("is-active", "--quiet", name, timeout=3)
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def easyeffects_installed(self) -> bool:
        try:
            result = self.runner.run(
                ["/usr/bin/flatpak", "info", APP_ID], timeout=6
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def device_info(self) -> DeviceInfo:
        return detect_device()

    def _read_setup_error(self) -> str:
        try:
            return self.setup_error_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _write_setup_error(self, value: str) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if value:
            self.setup_error_file.write_text(value, encoding="utf-8")
        else:
            self.setup_error_file.unlink(missing_ok=True)

    def state(self) -> RuntimeState:
        device = self.device_info()
        dependency = self.easyeffects_installed()
        headless_active = self._service_active(EE_SERVICE)
        kde_active = self._service_active(KDE_EE_SERVICE)
        ee_active = headless_active or kde_active
        session_active = self._service_active(SESSION_SERVICE)
        controller_active = self._service_active(CONTROLLER_SERVICE)
        gui_active = kde_active
        ready = bool(
            device.supported
            and dependency
            and session_active
            and ee_active
            and controller_active
        )

        if not device.supported:
            setup_state = "unsupported"
        elif not dependency:
            setup_state = "dependency-missing"
        elif ready:
            setup_state = "ready"
        else:
            setup_state = "repair-needed"

        return RuntimeState(
            device=device,
            easyeffects_installed=dependency,
            easyeffects_service_active=ee_active,
            controller_service_active=controller_active,
            gui_active=gui_active,
            runtime_ready=ready,
            setup_state=setup_state,
            setup_error=self._read_setup_error(),
        )

    def _atomic_text(self, path: Path, content: str, mode: int = 0o644) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.chmod(tmp, mode)
        os.replace(tmp, path)

    def _copy_if_changed(self, source: Path, target: Path, mode: int) -> bool:
        data = source.read_bytes()
        if target.exists() and target.read_bytes() == data:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.chmod(tmp, mode)
        os.replace(tmp, target)
        return True

    def _import_legacy_mode(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.mode_file.exists():
            return

        legacy = self.home / ".config" / LEGACY_CONFIG_DIRNAME / "mode"
        if legacy.exists():
            try:
                mode = normalize_mode(legacy.read_text(encoding="utf-8"))
            except OSError:
                mode = "auto"
        else:
            mode = "auto"
        self._atomic_text(self.mode_file, mode + "\n")

    def _disable_legacy_services(self) -> bool:
        changed = False
        for service in (LEGACY_CONTROLLER_SERVICE, LEGACY_EE_SERVICE):
            legacy_path = self.unit_dir / service
            if legacy_path.exists() or self._service_active(service):
                self._systemctl("disable", "--now", service, timeout=10)
                changed = True
        return changed

    def _kill_easyeffects(self) -> None:
        try:
            self.runner.run(
                ["/usr/bin/flatpak", "kill", APP_ID], timeout=6
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def _install_gui_wrapper(self) -> bool:
        """Install a normal KDE launcher; session handoff is automatic.

        In Desktop Mode the session manager already runs a graphical
        EasyEffects service with tray support. Launching the Flatpak again
        simply asks the existing single-instance application to show its
        window. No manual stop/start bridge is needed.
        """
        desktop = f"""[Desktop Entry]
Name=Easy Effects (ROG Ally Audio)
GenericName=Audio Effects
Comment=Open EasyEffects managed automatically by ROG Ally Audio
Exec=/usr/bin/flatpak run {APP_ID}
TryExec=/usr/bin/flatpak
Icon={APP_ID}
Terminal=false
Type=Application
Categories=AudioVideo;Audio;AudioVideoEditing;
Keywords=audio;effects;pipewire;equalizer;compressor;rog;ally;
StartupNotify=true
StartupWMClass=com.github.wwmm.easyeffects
NoDisplay=false
Hidden=false
"""
        changed = False
        current_desktop = (
            self.desktop_entry_target.read_text(encoding="utf-8")
            if self.desktop_entry_target.exists()
            else ""
        )
        if current_desktop != desktop:
            self._atomic_text(self.desktop_entry_target, desktop, 0o644)
            changed = True

        # Remove obsolete wrappers/sentinels from 0.1.7-0.1.10.
        if self.gui_wrapper_target.exists():
            self.gui_wrapper_target.unlink(missing_ok=True)
            changed = True
        self.gui_active_file.unlink(missing_ok=True)

        if self.legacy_desktop_entry_target.exists():
            try:
                legacy = self.legacy_desktop_entry_target.read_text(encoding="utf-8")
            except OSError:
                legacy = ""
            if "easyeffects-gui-wrapper.sh" in legacy:
                self.legacy_desktop_entry_target.unlink(missing_ok=True)
                changed = True
        return changed

    def _refresh_desktop_cache(self) -> None:
        """Refresh KDE/application caches after installing the GUI bridge.

        KDE can keep an old KService cache across plugin updates.  A valid
        ~/.local/share/applications desktop entry may therefore not become
        visible until the next login unless we explicitly rebuild the cache.
        Failures here are non-fatal because the desktop entry itself is still
        valid and will be discovered on the next normal cache refresh.
        """
        applications = self.home / ".local/share/applications"
        commands = (
            ["/usr/bin/update-desktop-database", str(applications)],
            ["/usr/bin/kbuildsycoca6", "--noincremental"],
            ["/usr/bin/kbuildsycoca5", "--noincremental"],
        )
        for command in commands:
            if not Path(command[0]).exists():
                continue
            try:
                self.runner.run(command, timeout=20)
            except (OSError, subprocess.SubprocessError):
                pass

    def _install_resources(self, force_presets: bool = False) -> bool:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.unit_dir.mkdir(parents=True, exist_ok=True)
        self._import_legacy_mode()

        changed = False
        gui_changed = self._install_gui_wrapper()
        changed |= gui_changed
        if gui_changed:
            self._refresh_desktop_cache()
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/controller.py",
            self.controller_target,
            0o755,
        )
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/session_manager.py",
            self.session_manager_target,
            0o755,
        )
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/easyeffects-kde.sh",
            self.kde_launcher_target,
            0o755,
        )
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/decky-rog-ally-audio-easyeffects.service",
            self.ee_unit_path,
            0o644,
        )
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/decky-rog-ally-audio-easyeffects-kde.service",
            self.kde_ee_unit_path,
            0o644,
        )
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/decky-rog-ally-audio-session.service",
            self.session_unit_path,
            0o644,
        )
        changed |= self._copy_if_changed(
            self.plugin_dir / "runtime/decky-rog-ally-audio-controller.service",
            self.controller_unit_path,
            0o644,
        )

        preset_results = self.preset_manager.install(force=force_presets)
        preset_changed = any(
            item.action in {"installed", "factory-updated", "reset-to-factory"}
            for item in preset_results
        )
        changed |= preset_changed

        manifest = {
            "plugin_version": PLUGIN_VERSION,
            "installed_at": int(time.time()),
            "preset_results": [item.to_dict() for item in preset_results],
        }
        self._atomic_text(
            self.install_manifest,
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )
        return changed

    def _wait_controller_ready(
        self,
        timeout: float = 14,
        *,
        min_updated_at: int = 0,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._service_active(SESSION_SERVICE) or not (self._service_active(EE_SERVICE) or self._service_active(KDE_EE_SERVICE)) or not self._service_active(CONTROLLER_SERVICE):
                time.sleep(0.25)
                continue
            try:
                data = json.loads(self.status_file.read_text(encoding="utf-8"))
                if (
                    isinstance(data, dict)
                    and data.get("controller_ok")
                    and data.get("easyeffects_service_active")
                    and int(data.get("updated_at") or 0) >= min_updated_at
                ):
                    return True
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
            time.sleep(0.25)
        return False

    def _require_systemctl(self, *args: str, timeout: float = 12) -> None:
        result = self._systemctl(*args, timeout=timeout)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "systemctl failed"
            raise RuntimeSetupError(f"systemctl --user {' '.join(args)}: {detail}")

    def bootstrap(self, *, force: bool = False, force_presets: bool = False) -> RuntimeState:
        """Install/repair the user runtime.

        Normal Decky startup is deliberately non-disruptive. It may install
        updated resource files and start a missing service, but it never stops
        or kills a healthy DSP runtime. This prevents plugin-loader reloads
        from interrupting audio mid-bootstrap.

        ``force=True`` is reserved for the explicit Repair action and performs
        a controlled full restart.
        """
        device = self.device_info()
        if not device.supported:
            raise UnsupportedDeviceError(device.support_reason)
        if not self.easyeffects_installed():
            raise MissingDependencyError("EasyEffects Flatpak is not installed")

        try:
            self._install_resources(force_presets=force_presets)
            legacy_changed = self._disable_legacy_services()
            self._require_systemctl("daemon-reload")

            session_active = self._service_active(SESSION_SERVICE)
            controller_active = self._service_active(CONTROLLER_SERVICE)
            min_updated_at = int(time.time()) - 2

            # The owner EasyEffects services are intentionally NOT enabled.
            # session_manager.py owns exactly one of them based on whether
            # plasmashell is running. This makes every KDE <-> Gaming Mode
            # transition automatic and prevents duplicate Flatpak instances.
            self._systemctl("disable", EE_SERVICE, KDE_EE_SERVICE, timeout=8)
            self._require_systemctl("enable", SESSION_SERVICE)
            self._require_systemctl("enable", CONTROLLER_SERVICE)

            if force:
                self._systemctl("stop", CONTROLLER_SERVICE, timeout=8)
                self._systemctl("stop", SESSION_SERVICE, timeout=8)
                self._systemctl("stop", KDE_EE_SERVICE, timeout=8)
                self._systemctl("stop", EE_SERVICE, timeout=8)
                self._kill_easyeffects()
                self._require_systemctl("restart", SESSION_SERVICE, timeout=10)
                # Give the session manager time to start the correct owner.
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if self._service_active(EE_SERVICE) or self._service_active(KDE_EE_SERVICE):
                        break
                    time.sleep(0.25)
                self._require_systemctl("restart", CONTROLLER_SERVICE, timeout=10)
            else:
                # Normal Decky startup never disrupts a healthy session.
                if not session_active:
                    self._require_systemctl("start", SESSION_SERVICE, timeout=10)
                if not controller_active:
                    self._require_systemctl("start", CONTROLLER_SERVICE, timeout=10)

            if not self._wait_controller_ready(min_updated_at=min_updated_at):
                state = self.state()
                raise RuntimeSetupError(
                    state.setup_error
                    or "controller did not confirm a live persistent EasyEffects service"
                )

            self._write_setup_error("")
            return self.state()
        except Exception as exc:
            self._write_setup_error(str(exc))
            raise

    def install_easyeffects(self) -> None:
        if self.easyeffects_installed():
            return

        # SteamOS normally already exposes Flathub. A user-scoped remote is
        # added only after an explicit Install action in the plugin UI.
        remotes = self.runner.run(
            ["/usr/bin/flatpak", "remotes", "--user", "--columns=name"],
            timeout=8,
        )
        names = {line.strip() for line in remotes.stdout.splitlines() if line.strip()}
        if "flathub" not in names:
            result = self.runner.run(
                [
                    "/usr/bin/flatpak",
                    "remote-add",
                    "--user",
                    "--if-not-exists",
                    "flathub",
                    "https://dl.flathub.org/repo/flathub.flatpakrepo",
                ],
                timeout=30,
            )
            if result.returncode != 0:
                raise MissingDependencyError(
                    result.stderr.strip() or "Could not add Flathub user remote"
                )

        result = self.runner.run(
            [
                "/usr/bin/flatpak",
                "install",
                "--user",
                "--noninteractive",
                "-y",
                "flathub",
                APP_ID,
            ],
            timeout=300,
        )
        if result.returncode != 0:
            raise MissingDependencyError(
                result.stderr.strip() or "EasyEffects installation failed"
            )

    def uninstall_runtime(self) -> None:
        for service in (CONTROLLER_SERVICE, SESSION_SERVICE, KDE_EE_SERVICE, EE_SERVICE):
            try:
                self._systemctl("disable", "--now", service, timeout=10)
            except Exception:
                pass
        self.ee_unit_path.unlink(missing_ok=True)
        self.kde_ee_unit_path.unlink(missing_ok=True)
        self.session_unit_path.unlink(missing_ok=True)
        self.controller_unit_path.unlink(missing_ok=True)
        self.controller_target.unlink(missing_ok=True)
        self.session_manager_target.unlink(missing_ok=True)
        self.kde_launcher_target.unlink(missing_ok=True)
        self.gui_wrapper_target.unlink(missing_ok=True)
        self.desktop_entry_target.unlink(missing_ok=True)
        # Remove the obsolete bridge desktop entry only if it is still our
        # wrapper; never delete Flatpak's exported application metadata.
        if self.legacy_desktop_entry_target.exists():
            try:
                legacy = self.legacy_desktop_entry_target.read_text(encoding="utf-8")
            except OSError:
                legacy = ""
            if "easyeffects-gui-wrapper.sh" in legacy:
                self.legacy_desktop_entry_target.unlink(missing_ok=True)
        try:
            self._systemctl("daemon-reload")
        except Exception:
            pass
        # Intentionally preserve EasyEffects itself, presets, mode and backups.
