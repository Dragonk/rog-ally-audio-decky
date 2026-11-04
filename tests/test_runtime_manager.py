from pathlib import Path

from backend.rog_ally_audio.runtime_manager import RuntimeManager


class DummyRunner:
    def run(self, args, *, timeout=15, check=False):  # pragma: no cover - not used here
        raise AssertionError(f"unexpected command: {args}")


def test_imports_legacy_mode_without_overwriting_new_mode(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    home = tmp_path / "deck"
    legacy = home / ".config/rog-ally-audio-controller"
    legacy.mkdir(parents=True)
    (legacy / "mode").write_text("cinema\n", encoding="utf-8")

    manager = RuntimeManager(plugin, home, runner=DummyRunner())
    manager._import_legacy_mode()
    assert manager.mode_file.read_text(encoding="utf-8") == "cinema\n"

    manager.mode_file.write_text("loud\n", encoding="utf-8")
    (legacy / "mode").write_text("balanced\n", encoding="utf-8")
    manager._import_legacy_mode()
    assert manager.mode_file.read_text(encoding="utf-8") == "loud\n"


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def run(self, args, *, timeout=15, check=False):
        self.calls.append(list(args))
        if args[:3] == ["/usr/bin/systemctl", "--user", "is-active"]:
            return Result(0)
        if args[:2] == ["/usr/bin/flatpak", "info"]:
            return Result(0)
        return Result(0)


def test_normal_bootstrap_never_stops_healthy_services_when_resources_change(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    (plugin / "runtime").mkdir(parents=True)
    (plugin / "presets").mkdir()
    home = tmp_path / "deck"
    runner = RecordingRunner()
    manager = RuntimeManager(plugin, home, runner=runner)

    monkeypatch.setattr(manager, "device_info", lambda: type("D", (), {"supported": True, "support_reason": ""})())
    monkeypatch.setattr(manager, "easyeffects_installed", lambda: True)
    monkeypatch.setattr(manager, "_install_resources", lambda force_presets=False: True)
    monkeypatch.setattr(manager, "_disable_legacy_services", lambda: False)
    monkeypatch.setattr(manager, "_service_active", lambda name: True)
    monkeypatch.setattr(manager, "_wait_controller_ready", lambda timeout=14, min_updated_at=0: True)
    monkeypatch.setattr(manager, "state", lambda: "ready")

    assert manager.bootstrap() == "ready"
    commands = [call[2:] for call in runner.calls if call[:2] == ["/usr/bin/systemctl", "--user"]]
    assert not any(cmd and cmd[0] in {"stop", "restart"} for cmd in commands)


def test_force_bootstrap_performs_controlled_restart(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    (plugin / "runtime").mkdir(parents=True)
    (plugin / "presets").mkdir()
    home = tmp_path / "deck"
    runner = RecordingRunner()
    manager = RuntimeManager(plugin, home, runner=runner)

    monkeypatch.setattr(manager, "device_info", lambda: type("D", (), {"supported": True, "support_reason": ""})())
    monkeypatch.setattr(manager, "easyeffects_installed", lambda: True)
    monkeypatch.setattr(manager, "_install_resources", lambda force_presets=False: False)
    monkeypatch.setattr(manager, "_disable_legacy_services", lambda: False)
    monkeypatch.setattr(manager, "_service_active", lambda name: True)
    monkeypatch.setattr(manager, "_kill_easyeffects", lambda: None)
    monkeypatch.setattr(manager, "_wait_controller_ready", lambda timeout=14, min_updated_at=0: True)
    monkeypatch.setattr(manager, "state", lambda: "ready")

    assert manager.bootstrap(force=True) == "ready"
    commands = [call[2:] for call in runner.calls if call[:2] == ["/usr/bin/systemctl", "--user"]]
    assert ["stop", "decky-rog-ally-audio-controller.service"] in commands
    assert ["stop", "decky-rog-ally-audio-easyeffects.service"] in commands
    assert ["stop", "decky-rog-ally-audio-easyeffects-kde.service"] in commands
    assert ["stop", "decky-rog-ally-audio-session.service"] in commands
    assert ["restart", "decky-rog-ally-audio-session.service"] in commands
    assert ["restart", "decky-rog-ally-audio-controller.service"] in commands


def test_stale_gui_sentinel_no_longer_blocks_automatic_session_manager(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    (plugin / "runtime").mkdir(parents=True)
    (plugin / "presets").mkdir()
    home = tmp_path / "deck"
    runner = RecordingRunner()
    manager = RuntimeManager(plugin, home, runner=runner)
    manager.gui_active_file.parent.mkdir(parents=True, exist_ok=True)
    manager.gui_active_file.write_text("1234\n", encoding="utf-8")

    monkeypatch.setattr(manager, "device_info", lambda: type("D", (), {"supported": True, "support_reason": ""})())
    monkeypatch.setattr(manager, "easyeffects_installed", lambda: True)
    monkeypatch.setattr(manager, "_install_resources", lambda force_presets=False: False)
    monkeypatch.setattr(manager, "_disable_legacy_services", lambda: False)
    monkeypatch.setattr(manager, "_service_active", lambda name: True)
    monkeypatch.setattr(manager, "_wait_controller_ready", lambda timeout=14, min_updated_at=0: True)
    monkeypatch.setattr(manager, "state", lambda: "ready")

    assert manager.bootstrap() == "ready"
    commands = [call[2:] for call in runner.calls if call[:2] == ["/usr/bin/systemctl", "--user"]]
    assert ["enable", "decky-rog-ally-audio-session.service"] in commands
    assert not any(cmd and cmd[0] in {"stop", "restart"} for cmd in commands)

