import json
import shutil
from pathlib import Path

from backend.rog_ally_audio.presets import PresetManager, sha256_file

ROOT = Path(__file__).resolve().parents[1]


def make_plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "plugin"
    shutil.copytree(ROOT / "presets", plugin / "presets")
    return plugin


def test_first_install_creates_factory_presets(tmp_path):
    home = tmp_path / "home"
    data = home / ".local/share/decky-rog-ally-audio"
    manager = PresetManager(make_plugin(tmp_path), home, data)

    results = manager.install()
    assert {r.action for r in results} == {"installed"}
    assert all(r.managed for r in results)
    assert manager.manifest_path.exists()


def test_unknown_user_modified_preset_is_never_overwritten(tmp_path):
    home = tmp_path / "home"
    data = home / ".local/share/decky-rog-ally-audio"
    plugin = make_plugin(tmp_path)
    manager = PresetManager(plugin, home, data)
    manager.target_dir.mkdir(parents=True)

    target = manager.target_dir / "ROG Xbox Ally X - Experimental Balanced.json"
    target.write_text('{"output":{"plugins_order":["my_custom_effect"]}}', encoding="utf-8")
    before = sha256_file(target)

    results = manager.install()
    balanced = next(r for r in results if r.mode == "balanced")
    assert balanced.action == "preserved-user-version"
    assert not balanced.managed
    assert sha256_file(target) == before


def test_force_reset_backs_up_and_restores_factory(tmp_path):
    home = tmp_path / "home"
    data = home / ".local/share/decky-rog-ally-audio"
    plugin = make_plugin(tmp_path)
    manager = PresetManager(plugin, home, data)
    manager.target_dir.mkdir(parents=True)

    target = manager.target_dir / "ROG Xbox Ally X - Experimental Balanced.json"
    target.write_text('{"output":{"plugins_order":["custom"]}}', encoding="utf-8")

    results = manager.install(force=True)
    balanced = next(r for r in results if r.mode == "balanced")
    assert balanced.action == "reset-to-factory"
    assert balanced.managed
    assert json.loads(target.read_text(encoding="utf-8"))["output"]["filter#0"]["frequency"] == 85.0
    assert list(manager.backup_root.rglob(target.name))
