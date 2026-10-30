"""Gera o instalador: dist/AureumIsland-Setup-<versão>.exe.

    .venv\\Scripts\\python scripts\\build.py              # app + instalador
    .venv\\Scripts\\python scripts\\build.py --no-installer

1. Lê a versão do pyproject.toml.
2. Gera em build/ o ícone (.ico, a partir de assets/icons/app.svg) e o version info do exe.
3. PyInstaller em modo pasta (packaging/aureum_island.spec) -> dist/AureumIsland/.
4. Inno Setup (packaging/aureum-island.iss) -> dist/AureumIsland-Setup-<versão>.exe.

Precisa do PyInstaller (dependência de dev) e do Inno Setup 6 (winget JRSoftware.InnoSetup).
Ver docs/decisions/0011-empacotamento.md.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
ICON = BUILD / "aureum-island.ico"
VERSION_INFO = BUILD / "version_info.txt"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def numeric_version(text: str) -> tuple[int, int, int, int]:
    """'0.1.0' -> (0, 1, 0, 0). Sufixos como 'b1' saem: o VERSIONINFO só aceita números."""
    parts = [int(n) for n in re.findall(r"\d+", text.split("-")[0].split("+")[0])[:4]]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


# --- ícone -------------------------------------------------------------------------


def render_icon_pngs() -> list[tuple[int, bytes]]:
    """O app.svg em accent sobre bg-rail (paleta escura, como o notch), num quadrado arredondado."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "src"))
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    from aureum_island.theme.tokens import DARK, DEFAULT_ACCENT

    _app = QGuiApplication.instance() or QGuiApplication([])
    svg = (ROOT / "src/aureum_island/assets/icons/app.svg").read_text("utf-8")
    renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", DEFAULT_ACCENT).encode()))
    pngs = []
    for size in ICO_SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(DARK.bg_rail))
        p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        pad = size * (0.12 if size <= 24 else 0.16)
        renderer.render(p, QRectF(pad, pad, size - 2 * pad, size - 2 * pad))
        p.end()
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf, "PNG")
        pngs.append((size, bytes(data)))
    return pngs


def write_ico(path: Path, pngs: list[tuple[int, bytes]]) -> None:
    """ICO com imagens PNG dentro (aceito desde o Windows Vista), sem lib extra."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, png in pngs:
        dim = 0 if size >= 256 else size  # 0 quer dizer 256
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    path.write_bytes(header + entries + blobs)


# --- version info ------------------------------------------------------------------


def write_version_info(path: Path, text: str) -> None:
    nums = numeric_version(text)
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'Aureum'),
      StringStruct('FileDescription', 'Aureum Island'),
      StringStruct('FileVersion', '{text}'),
      StringStruct('InternalName', 'AureumIsland'),
      StringStruct('LegalCopyright', '© 2026 Aureum'),
      StringStruct('OriginalFilename', 'AureumIsland.exe'),
      StringStruct('ProductName', 'Aureum Island'),
      StringStruct('ProductVersion', '{text}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


# --- Inno Setup ----------------------------------------------------------------------


def find_iscc() -> Path | None:
    candidates = [
        os.environ.get("ISCC"),
        shutil.which("ISCC"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Inno Setup 6/ISCC.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Inno Setup 6/ISCC.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-installer", action="store_true", help="só o PyInstaller")
    args = parser.parse_args()

    text = version()
    print(f"Aureum Island {text}")
    BUILD.mkdir(exist_ok=True)
    write_ico(ICON, render_icon_pngs())
    write_version_info(VERSION_INFO, text)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(ROOT / "packaging/aureum_island.spec"),
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(BUILD / "pyinstaller"),
        ],
        check=True,
        cwd=ROOT,
    )
    app_dir = DIST / "AureumIsland"
    print(f"app: {app_dir}")
    if args.no_installer:
        return 0

    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup 6 não encontrado (winget install JRSoftware.InnoSetup --scope user).")
        return 1
    subprocess.run(
        [
            str(iscc),
            "/Q",
            f"/DAppVersion={text}",
            f"/DSourceDir={app_dir}",
            f"/DOutputDir={DIST}",
            f"/DIconFile={ICON}",
            str(ROOT / "packaging/aureum-island.iss"),
        ],
        check=True,
        cwd=ROOT,
    )
    print(f"instalador: {DIST / f'AureumIsland-Setup-{text}.exe'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
