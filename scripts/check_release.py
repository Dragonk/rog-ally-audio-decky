#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
backend_version = (ROOT / "backend/rog_ally_audio/__init__.py").read_text(encoding="utf-8")
constants = (ROOT / "backend/rog_ally_audio/constants.py").read_text(encoding="utf-8")
version = package["version"]
assert f'__version__ = "{version}"' in backend_version
assert f'PLUGIN_VERSION = "{version}"' in constants
print(version)
