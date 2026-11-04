import json
from pathlib import Path

from backend.rog_ally_audio import __version__
from backend.rog_ally_audio.constants import PLUGIN_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_versions_match():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == __version__ == PLUGIN_VERSION == "0.1.11"


def test_release_workflow_will_publish_decky_zip():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "gh release create" in workflow
    assert "ROGAllyAudio-v${VERSION}.zip" in workflow
    assert "permissions:\n  contents: write" in workflow
