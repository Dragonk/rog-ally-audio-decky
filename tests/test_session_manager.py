from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("session_manager", ROOT / "runtime/session_manager.py")
assert SPEC and SPEC.loader
sm = module_from_spec(SPEC)
SPEC.loader.exec_module(sm)


def test_healthy_kde_requires_only_graphical_owner(monkeypatch):
    states = {
        sm.KDE_SERVICE: True,
        sm.HEADLESS_SERVICE: False,
        sm.CONTROLLER_SERVICE: True,
    }
    monkeypatch.setattr(sm, "active", lambda name: states.get(name, False))
    assert sm.healthy_for("kde") is True
    states[sm.HEADLESS_SERVICE] = True
    assert sm.healthy_for("kde") is False


def test_healthy_gaming_requires_only_headless_owner(monkeypatch):
    states = {
        sm.KDE_SERVICE: False,
        sm.HEADLESS_SERVICE: True,
        sm.CONTROLLER_SERVICE: True,
    }
    monkeypatch.setattr(sm, "active", lambda name: states.get(name, False))
    assert sm.healthy_for("gaming") is True
    states[sm.KDE_SERVICE] = True
    assert sm.healthy_for("gaming") is False


def test_kde_switch_enables_tray_and_starts_graphical_owner(monkeypatch):
    calls = []
    monkeypatch.setattr(sm, "write_state", lambda *args: calls.append(("state",) + args))
    monkeypatch.setattr(sm, "configure_common", lambda: calls.append(("common",)))
    monkeypatch.setattr(sm, "dconf_bool", lambda k, v: calls.append(("dconf", k, v)))
    monkeypatch.setattr(sm, "systemctl", lambda *args, **kwargs: calls.append(("systemctl",) + args) or type("R", (), {"returncode": 0})())
    monkeypatch.setattr(sm, "kill_ee", lambda: calls.append(("kill",)))
    monkeypatch.setattr(sm, "wait_active", lambda service, timeout=12: True)
    assert sm.switch_to_kde() is True
    assert ("dconf", "show-tray-icon", True) in calls
    assert ("systemctl", "stop", sm.HEADLESS_SERVICE) in calls
    assert ("systemctl", "restart", sm.KDE_SERVICE) in calls
    assert ("systemctl", "start", sm.CONTROLLER_SERVICE) in calls


def test_gaming_switch_disables_tray_and_starts_headless_owner(monkeypatch):
    calls = []
    monkeypatch.setattr(sm, "write_state", lambda *args: calls.append(("state",) + args))
    monkeypatch.setattr(sm, "configure_common", lambda: calls.append(("common",)))
    monkeypatch.setattr(sm, "dconf_bool", lambda k, v: calls.append(("dconf", k, v)))
    monkeypatch.setattr(sm, "systemctl", lambda *args, **kwargs: calls.append(("systemctl",) + args) or type("R", (), {"returncode": 0})())
    monkeypatch.setattr(sm, "kill_ee", lambda: calls.append(("kill",)))
    monkeypatch.setattr(sm, "wait_active", lambda service, timeout=12: True)
    assert sm.switch_to_gaming() is True
    assert ("dconf", "show-tray-icon", False) in calls
    assert ("systemctl", "stop", sm.KDE_SERVICE) in calls
    assert ("systemctl", "restart", sm.HEADLESS_SERVICE) in calls
    assert ("systemctl", "start", sm.CONTROLLER_SERVICE) in calls
