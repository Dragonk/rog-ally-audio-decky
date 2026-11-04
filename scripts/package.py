#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def version() -> str:
    return json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]


def add_tree(archive: zipfile.ZipFile, source: Path, prefix: str = "") -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(source)
        archive.write(path, str(Path(prefix) / rel))


def main() -> int:
    dist = ROOT / "dist/index.js"
    if not dist.exists():
        print("dist/index.js is missing; run pnpm build first", file=sys.stderr)
        return 2

    BUILD.mkdir(parents=True, exist_ok=True)
    output = BUILD / f"ROGAllyAudio-v{version()}.zip"
    output.unlink(missing_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for filename in (
            "main.py",
            "plugin.json",
            "package.json",
            "LICENSE",
            "README.md",
        ):
            zf.write(ROOT / filename, filename)
        zf.write(dist, "dist/index.js")
        add_tree(zf, ROOT / "backend", "backend")
        add_tree(zf, ROOT / "runtime", "runtime")
        add_tree(zf, ROOT / "presets", "presets")
        if (ROOT / "assets/thumbnail.png").exists():
            zf.write(ROOT / "assets/thumbnail.png", "assets/thumbnail.png")

    alias = BUILD / "ROGAllyAudio.zip"
    alias.unlink(missing_ok=True)
    alias.write_bytes(output.read_bytes())

    print(output)
    print(alias)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
