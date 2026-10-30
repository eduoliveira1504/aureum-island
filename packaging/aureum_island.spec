# PyInstaller: modo pasta (onedir), sem console. Rode por scripts/build.py, que gera antes
# o ícone e o version info em build/. Ver docs/decisions/0011-empacotamento.md.
# ruff: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"
BUILD = ROOT / "build"

# Só os assets (fontes, ícones, som); o código entra pela análise de imports.
datas = [
    (str(path), str(path.parent.relative_to(SRC)))
    for path in (SRC / "aureum_island" / "assets").rglob("*")
    if path.is_file() and path.suffix not in {".py", ".pyc"}
]
# zoneinfo no Windows lê os fusos do pacote tzdata (eventos ICS com TZID).
datas += collect_data_files("tzdata")

hiddenimports = collect_submodules("winrt") + collect_submodules("tzdata")

# Módulos Qt que o app não usa. Os hooks do PySide6 só puxam o que é importado, mas
# isso garante que nada grande entre por dependência indireta.
QT_EXCLUDES = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras", "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic", "PySide6.Qt3DRender", "PySide6.QtBluetooth", "PySide6.QtCharts",
    "PySide6.QtConcurrent", "PySide6.QtDataVisualization", "PySide6.QtDBus",
    "PySide6.QtDesigner", "PySide6.QtGraphs", "PySide6.QtGraphsWidgets", "PySide6.QtHelp",
    "PySide6.QtHttpServer", "PySide6.QtLocation", "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth", "PySide6.QtNfc", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtPositioning", "PySide6.QtPrintSupport",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSerialBus", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtSvgWidgets",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtUiTools", "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "PySide6.QtWebView", "PySide6.QtXml",
]
EXCLUDES = QT_EXCLUDES + ["tkinter", "unittest", "pydoc", "pytest", "pytestqt", "ruff"]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=EXCLUDES,
    noarchive=False,
)

# Traduções do Qt: só as em português (o app é pt-BR).
a.datas = [
    entry
    for entry in a.datas
    if not (
        "translations" in entry[0].replace("\\", "/")
        and entry[0].endswith(".qm")
        and "_pt" not in Path(entry[0]).name
    )
]

# Plugins e DLLs que os hooks trazem e o app não usa. O teclado virtual puxa Quick e Qml;
# o qpdf puxa o Qt6Pdf; sem o ffmpeg, o som (QSoundEffect, .wav) usa o backend do Windows.
DROP_BINARIES = {
    "opengl32sw.dll", "qtvirtualkeyboardplugin.dll", "qtuiotouchplugin.dll", "qpdf.dll",
    "qdirect2d.dll", "qminimal.dll", "qicns.dll", "qtiff.dll", "qwebp.dll", "qtga.dll",
    "qwbmp.dll", "qgif.dll", "qjpeg.dll", "ffmpegmediaplugin.dll", "qopensslbackend.dll",
    "qcertonlybackend.dll",
}
DROP_PREFIXES = (
    "qt6quick", "qt6qml", "qt6pdf", "qt6virtualkeyboard", "qt6opengl", "avcodec", "avformat",
    "avutil", "swscale", "swresample",
)


def _keep(entry) -> bool:
    name = Path(entry[0]).name.lower()
    return name not in DROP_BINARIES and not name.startswith(DROP_PREFIXES)


a.binaries = [entry for entry in a.binaries if _keep(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AureumIsland",
    console=False,
    icon=str(BUILD / "aureum-island.ico"),
    version=str(BUILD / "version_info.txt"),
    upx=False,  # UPX aumenta os falsos positivos de antivírus
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="AureumIsland",
    upx=False,
)
