from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .constants import PLUGIN_VERSION, PROFILE_FILENAMES


@dataclass
class PresetInstallResult:
    mode: str
    target: str
    action: str
    managed: bool
    shipped_sha256: str
    current_sha256: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PresetManager:
    def __init__(self, plugin_dir: Path, home: Path, data_dir: Path):
        self.plugin_dir = Path(plugin_dir)
        self.home = Path(home)
        self.data_dir = Path(data_dir)
        self.source_dir = self.plugin_dir / "presets"
        self.target_dir = (
            self.home
            / ".var/app/com.github.wwmm.easyeffects/data/easyeffects/output"
        )
        self.manifest_path = self.data_dir / "factory-presets.json"
        self.backup_root = self.data_dir / "backups/presets"

    def _read_manifest(self) -> dict:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_manifest(self, results: list[PresetInstallResult]) -> None:
        managed_hashes = {
            item.mode: item.shipped_sha256
            for item in results
            if item.managed
        }
        data = {
            "plugin_version": PLUGIN_VERSION,
            "managed_factory_hashes": managed_hashes,
            "results": [item.to_dict() for item in results],
            "updated_at": int(time.time()),
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.manifest_path)

    def _backup(self, target: Path) -> None:
        if not target.exists():
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        folder = self.backup_root / stamp
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, folder / target.name)

    def install(self, force: bool = False) -> list[PresetInstallResult]:
        self.target_dir.mkdir(parents=True, exist_ok=True)
        previous = self._read_manifest().get("managed_factory_hashes", {})
        if not isinstance(previous, dict):
            previous = {}

        results: list[PresetInstallResult] = []

        for mode, filename in PROFILE_FILENAMES.items():
            source = self.source_dir / filename
            target = self.target_dir / filename
            shipped = sha256_file(source)
            current = sha256_file(target) if target.exists() else ""
            previous_factory = str(previous.get(mode, ""))

            if not target.exists():
                shutil.copy2(source, target)
                action = "installed"
                managed = True
                current = shipped
            elif force:
                self._backup(target)
                shutil.copy2(source, target)
                action = "reset-to-factory"
                managed = True
                current = shipped
            elif current == shipped:
                action = "already-current"
                managed = True
            elif previous_factory and current == previous_factory:
                self._backup(target)
                shutil.copy2(source, target)
                action = "factory-updated"
                managed = True
                current = shipped
            else:
                # Never overwrite an unrecognized/user-edited preset during a
                # normal plugin upgrade.
                action = "preserved-user-version"
                managed = False

            results.append(
                PresetInstallResult(
                    mode=mode,
                    target=str(target),
                    action=action,
                    managed=managed,
                    shipped_sha256=shipped,
                    current_sha256=current,
                )
            )

        self._write_manifest(results)
        return results
