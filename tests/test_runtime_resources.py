from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_headless_unit_keeps_proven_offscreen_runtime():
    ee = (ROOT / "runtime/decky-rog-ally-audio-easyeffects.service").read_text(encoding="utf-8")
    assert "--service-mode --hide-window" in ee
    assert "QT_QPA_PLATFORM=offscreen" in ee
    assert "--command=easyeffects" in ee
    assert "Restart=always" in ee
    assert "WantedBy=" not in ee


def test_kde_unit_uses_graphical_session_wrapper_and_is_not_enabled_directly():
    unit = (ROOT / "runtime/decky-rog-ally-audio-easyeffects-kde.service").read_text(encoding="utf-8")
    wrapper = (ROOT / "runtime/easyeffects-kde.sh").read_text(encoding="utf-8")
    assert "easyeffects-kde.sh" in unit
    assert "WantedBy=" not in unit
    assert "plasmashell" in wrapper
    assert "/proc/$PID/environ" in wrapper
    assert 'QT_QPA_PLATFORM="wayland"' in wrapper
    assert "--service-mode --hide-window" in wrapper


def test_session_manager_owns_automatic_kde_gaming_handoff():
    manager = (ROOT / "runtime/session_manager.py").read_text(encoding="utf-8")
    assert '"plasmashell"' in manager
    assert "switch_to_kde" in manager
    assert "switch_to_gaming" in manager
    assert "org.kde.StatusNotifierWatcher" in manager
    assert 'dconf_bool("show-tray-icon", True)' in manager
    assert 'dconf_bool("show-tray-icon", False)' in manager
    assert 'dconf_bool("autostart-on-login", False)' in manager
    assert "flatpak\", \"kill" in manager


def test_controller_unit_depends_on_session_manager_not_headless_owner():
    unit = (ROOT / "runtime/decky-rog-ally-audio-controller.service").read_text(encoding="utf-8")
    assert "%h/.local/share/decky-rog-ally-audio/controller.py" in unit
    assert "decky-rog-ally-audio-session.service" in unit
    assert "Wants=pipewire-pulse.service decky-rog-ally-audio-session.service" in unit


def test_controller_accepts_either_easyeffects_owner():
    controller = (ROOT / "runtime/controller.py").read_text(encoding="utf-8")
    assert "KDE_EE_SERVICE" in controller
    assert "active_easyeffects_runtime" in controller
    assert "desktop_session_mode" in controller
    assert 'target = KDE_EE_SERVICE if desktop_session_mode() == "kde" else EE_SERVICE' in controller
    assert '"easyeffects_runtime": active_easyeffects_runtime()' in controller


def test_plugin_manifest_has_no_root_flag():
    import json

    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["api_version"] == 1
    assert "root" not in manifest.get("flags", [])
    assert "_root" not in manifest.get("flags", [])


def test_runtime_installs_direct_kde_launcher_and_session_resources():
    manager = (ROOT / "backend/rog_ally_audio/runtime_manager.py").read_text(encoding="utf-8")
    assert "session_manager.py" in manager
    assert "easyeffects-kde.sh" in manager
    assert "decky-rog-ally-audio-easyeffects-kde.service" in manager
    assert "decky-rog-ally-audio-session.service" in manager
    assert f"Exec=/usr/bin/flatpak run" in manager
    assert "easyeffects-gui-wrapper.sh" in manager  # legacy cleanup only
    assert "Remove obsolete wrappers/sentinels" in manager


def test_kde_launcher_refreshes_desktop_cache_and_has_required_metadata():
    manager = (ROOT / "backend/rog_ally_audio/runtime_manager.py").read_text(encoding="utf-8")
    assert "_refresh_desktop_cache" in manager
    assert "update-desktop-database" in manager
    assert "kbuildsycoca6" in manager
    assert "StartupWMClass=com.github.wwmm.easyeffects" in manager
    assert "NoDisplay=true" not in manager


def test_controller_has_live_dsp_self_heal_watchdog():
    controller = (ROOT / "runtime/controller.py").read_text(encoding="utf-8")
    assert "dsp_requires_self_heal" in controller
    assert "DSP self-heal" in controller
    assert "self_heal_count" in controller
