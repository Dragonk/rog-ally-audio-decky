#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config" / "rog-ally-audio"
STATE_FILE = CONFIG / "session.json"
APP_ID = "com.github.wwmm.easyeffects"
HEADLESS_SERVICE = "decky-rog-ally-audio-easyeffects.service"
KDE_SERVICE = "decky-rog-ally-audio-easyeffects-kde.service"
CONTROLLER_SERVICE = "decky-rog-ally-audio-controller.service"
RUNTIME = f"/run/user/{os.getuid()}"
ENV = {
    "HOME": str(HOME),
    "USER": os.environ.get("USER", HOME.name),
    "LOGNAME": os.environ.get("LOGNAME", HOME.name),
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin:/bin",
    "XDG_RUNTIME_DIR": RUNTIME,
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path={RUNTIME}/bus",
    "LANG": "C.UTF-8",
}


def run(args: list[str], timeout: float = 12) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=ENV,
    )


def systemctl(*args: str, timeout: float = 12) -> subprocess.CompletedProcess[str]:
    return run(["/usr/bin/systemctl", "--user", *args], timeout)


def active(service: str) -> bool:
    try:
        return systemctl("is-active", "--quiet", service, timeout=3).returncode == 0
    except Exception:
        return False


def kde_running() -> bool:
    try:
        result = run(
            ["/usr/bin/pgrep", "-u", str(os.getuid()), "-x", "plasmashell"],
            timeout=2,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def write_state(mode: str, phase: str, error: str = "") -> None:
    atomic_json(
        STATE_FILE,
        {
            "mode": mode,
            "phase": phase,
            "headless_active": active(HEADLESS_SERVICE),
            "kde_active": active(KDE_SERVICE),
            "controller_active": active(CONTROLLER_SERVICE),
            "error": error,
            "updated_at": int(time.time()),
        },
    )


def dconf_bool(key: str, value: bool) -> None:
    run(
        [
            "/usr/bin/dconf",
            "write",
            f"/com/github/wwmm/easyeffects/{key}",
            "true" if value else "false",
        ],
        timeout=4,
    )


def configure_common() -> None:
    # ROG Ally Audio owns startup. EasyEffects' own autostart would create a
    # second instance and race the Desktop/Gaming session handoff.
    dconf_bool("enable-service-mode", True)
    dconf_bool("autostart-on-login", False)
    dconf_bool("process-all-inputs", False)

    # EasyEffects 8.x needs StatusNotifierWatcher access for the tray from the
    # Flatpak sandbox. Running this here (outside Decky/PyInstaller) is safe and
    # idempotent, and makes Desktop Mode require zero manual setup.
    try:
        run(
            [
                "/usr/bin/flatpak",
                "override",
                "--user",
                APP_ID,
                "--talk-name=org.kde.StatusNotifierWatcher",
            ],
            timeout=8,
        )
    except Exception:
        pass

    autostart = HOME / ".config/autostart/com.github.wwmm.easyeffects.desktop"
    try:
        autostart.unlink(missing_ok=True)
    except OSError:
        pass


def wait_active(service: str, timeout: float = 12) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if active(service):
            return True
        time.sleep(0.2)
    return False


def kill_ee() -> None:
    try:
        run(["/usr/bin/flatpak", "kill", APP_ID], timeout=6)
    except Exception:
        pass


def switch_to_kde() -> bool:
    write_state("kde", "switching")
    configure_common()
    dconf_bool("show-tray-icon", True)
    dconf_bool("no-window-after-starting", True)

    systemctl("stop", CONTROLLER_SERVICE, timeout=8)
    systemctl("stop", HEADLESS_SERVICE, timeout=8)
    kill_ee()
    systemctl("reset-failed", KDE_SERVICE, timeout=5)
    systemctl("restart", KDE_SERVICE, timeout=12)
    if not wait_active(KDE_SERVICE, 12):
        write_state("kde", "error", "KDE EasyEffects service did not start")
        return False
    systemctl("start", CONTROLLER_SERVICE, timeout=10)
    if not wait_active(CONTROLLER_SERVICE, 8):
        write_state("kde", "error", "controller did not start after KDE handoff")
        return False
    write_state("kde", "ready")
    return True


def switch_to_gaming() -> bool:
    write_state("gaming", "switching")
    configure_common()
    # There is no system tray in Gaming Mode. Keep the proven offscreen
    # service and do not ask Qt to create tray objects there.
    dconf_bool("show-tray-icon", False)
    dconf_bool("no-window-after-starting", True)

    systemctl("stop", CONTROLLER_SERVICE, timeout=8)
    systemctl("stop", KDE_SERVICE, timeout=8)
    kill_ee()
    systemctl("reset-failed", HEADLESS_SERVICE, timeout=5)
    systemctl("restart", HEADLESS_SERVICE, timeout=12)
    if not wait_active(HEADLESS_SERVICE, 12):
        write_state("gaming", "error", "headless EasyEffects service did not start")
        return False
    systemctl("start", CONTROLLER_SERVICE, timeout=10)
    if not wait_active(CONTROLLER_SERVICE, 8):
        write_state("gaming", "error", "controller did not start after Gaming handoff")
        return False
    write_state("gaming", "ready")
    return True


def healthy_for(target: str) -> bool:
    if target == "kde":
        return active(KDE_SERVICE) and not active(HEADLESS_SERVICE) and active(CONTROLLER_SERVICE)
    return active(HEADLESS_SERVICE) and not active(KDE_SERVICE) and active(CONTROLLER_SERVICE)


def main() -> int:
    CONFIG.mkdir(parents=True, exist_ok=True)
    configure_common()
    current = ""
    while True:
        target = "kde" if kde_running() else "gaming"
        if target != current or not healthy_for(target):
            ok = switch_to_kde() if target == "kde" else switch_to_gaming()
            if ok:
                current = target
            else:
                time.sleep(2.0)
                continue
        else:
            write_state(target, "ready")
        time.sleep(1.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
