"""Atualização automática pelos releases do GitHub, igual ao Aureum Voice.

Procura ao abrir e a cada 6 h (só no app instalado), baixa o instalador em segundo plano,
confere o SHA-256 que o GitHub publica para cada arquivo do release e avisa. "Reiniciar"
roda o instalador em modo silencioso, que reabre o app na versão nova. Se o usuário não
reiniciar, a atualização entra quando ele sair pelo "Sair" da bandeja (sem reabrir).
Sem internet ou com o GitHub fora: tenta de novo na próxima checagem, sem avisar.
Ver docs/decisions/0012-atualizacao-automatica.md.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

from aureum_island.version import user_agent

log = logging.getLogger(__name__)

REPO = "eduoliveira1504/aureum-island"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY_MS = 6 * 60 * 60 * 1000
FIRST_CHECK_MS = 5_000  # depois que o app terminou de abrir
TIMEOUT_MS = 15_000
MAX_INSTALLER_BYTES = 200 * 1024 * 1024
ASSET_RE = re.compile(r"^AureumIsland-Setup-(?P<version>[0-9][0-9A-Za-z.\-]*)\.exe$")
# Instalador do Inno em modo silencioso; /RELAUNCH=1 reabre o app no fim (ver o .iss).
INSTALL_ARGS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")


def parse_version(text: str) -> tuple[int, ...] | None:
    """'v0.2.0' -> (0, 2, 0). Versão com sufixo (pré-release) não conta: None."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(n) for n in match.group(1).split(".")) if match else None


def is_newer(candidate: str, current: str) -> bool:
    new, cur = parse_version(candidate), parse_version(current)
    if new is None or cur is None:
        return False
    width = max(len(new), len(cur))
    return new + (0,) * (width - len(new)) > cur + (0,) * (width - len(cur))


@dataclass(frozen=True)
class Release:
    version: str
    name: str  # nome do arquivo do instalador
    url: str
    size: int
    sha256: str


def pick_release(payload: Any, current: str) -> Release | None:
    """O instalador do último release, se for mais novo que `current` e tiver SHA-256."""
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None
    tag = str(payload.get("tag_name", ""))
    if not is_newer(tag, current):
        return None
    for asset in payload.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        match = ASSET_RE.match(str(asset.get("name", "")))
        digest = str(asset.get("digest") or "")
        if not match or not digest.startswith("sha256:"):
            continue
        size = asset.get("size")
        url = asset.get("browser_download_url")
        if not isinstance(size, int) or not 0 < size <= MAX_INSTALLER_BYTES or not url:
            continue
        return Release(tag.lstrip("v"), asset["name"], str(url), size, digest[7:].lower())
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Http(Protocol):
    def get_json(self, url: str, callback: Callable[[Any], None]) -> None:
        """callback(dados) ou callback(None) se falhou."""

    def download(self, url: str, path: Path, callback: Callable[[bool], None]) -> None:
        """Salva em `path`; callback(True) se baixou inteiro."""


class QtHttp:
    """QNetworkAccessManager, no loop do Qt (sem thread e sem lib nova)."""

    def __init__(self, parent: QObject) -> None:
        from PySide6.QtNetwork import QNetworkAccessManager

        self._nam = QNetworkAccessManager(parent)
        self._nam.setTransferTimeout(TIMEOUT_MS)
        self._agent = user_agent().encode()

    def _request(self, url: str, accept: bytes):
        from PySide6.QtNetwork import QNetworkRequest

        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", self._agent)
        request.setRawHeader(b"Accept", accept)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        return request

    def get_json(self, url: str, callback: Callable[[Any], None]) -> None:
        from PySide6.QtNetwork import QNetworkReply

        reply = self._nam.get(self._request(url, b"application/vnd.github+json"))

        def done() -> None:
            data = None
            if reply.error() == QNetworkReply.NetworkError.NoError:
                try:
                    data = json.loads(bytes(reply.readAll()))
                except ValueError:
                    data = None
            else:
                log.info("atualização: checagem falhou (%s)", reply.error().name)
            reply.deleteLater()
            callback(data)

        reply.finished.connect(done)

    def download(self, url: str, path: Path, callback: Callable[[bool], None]) -> None:
        from PySide6.QtNetwork import QNetworkReply

        path.parent.mkdir(parents=True, exist_ok=True)
        out = path.open("wb")
        reply = self._nam.get(self._request(url, b"application/octet-stream"))
        reply.readyRead.connect(lambda: out.write(bytes(reply.readAll())))

        def done() -> None:
            out.write(bytes(reply.readAll()))
            out.close()
            ok = reply.error() == QNetworkReply.NetworkError.NoError
            if not ok:
                log.info("atualização: download falhou (%s)", reply.error().name)
            reply.deleteLater()
            callback(ok)

        reply.finished.connect(done)


class Updater(QObject):
    ready = Signal(str)  # versão baixada e conferida, pronta para instalar

    def __init__(
        self,
        updates_dir: Path,
        *,
        current: str,
        enabled: bool,
        http: Http | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._dir = updates_dir
        self.current = current
        self.enabled = enabled
        self._http = http
        self._busy = False
        self.ready_version: str | None = None
        self.installer: Path | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check)

    def start(self) -> None:
        """Só no app instalado: a primeira checagem logo depois de abrir, depois a cada 6 h."""
        if not self.enabled:
            return
        self._clean_old()
        if self._http is None:
            self._http = QtHttp(self)
        QTimer.singleShot(FIRST_CHECK_MS, self.check)
        self._timer.start(CHECK_EVERY_MS)

    def check(self) -> None:
        if self._busy or self._http is None:
            return
        self._busy = True
        self._http.get_json(LATEST_URL, self._on_latest)

    def _on_latest(self, payload: Any) -> None:
        release = pick_release(payload, self.current)
        if release is None or release.version == self.ready_version:
            self._busy = False
            return
        target = self._dir / release.name
        if target.is_file() and self._verified(target, release):
            self._set_ready(release, target)  # já baixado numa sessão anterior
            return
        part = target.with_name(target.name + ".part")
        log.info("atualização: baixando a versão %s", release.version)
        self._http.download(release.url, part, lambda ok: self._on_downloaded(ok, release, part))

    def _on_downloaded(self, ok: bool, release: Release, part: Path) -> None:
        target = self._dir / release.name
        if ok and self._verified(part, release):
            part.replace(target)
            self._set_ready(release, target)
            return
        if ok:
            log.warning(
                "atualização: arquivo da versão %s não confere; descartado", release.version
            )
        part.unlink(missing_ok=True)
        self._busy = False

    @staticmethod
    def _verified(path: Path, release: Release) -> bool:
        return path.stat().st_size == release.size and sha256_of(path) == release.sha256

    def _set_ready(self, release: Release, path: Path) -> None:
        self._busy = False
        self.ready_version, self.installer = release.version, path
        log.info("atualização: versão %s pronta", release.version)
        self.ready.emit(release.version)

    def _clean_old(self) -> None:
        """Instaladores de versões que já estão instaladas (ou downloads pela metade)."""
        if not self._dir.is_dir():
            return
        for path in self._dir.iterdir():
            match = ASSET_RE.match(path.name)
            if path.suffix == ".part" or (match and not is_newer(match["version"], self.current)):
                path.unlink(missing_ok=True)

    def launch_installer(self, *, relaunch: bool) -> bool:
        """Roda o instalador baixado em modo silencioso, solto do app (que já está saindo e
        já soltou a trava de instância única). `relaunch`: reabrir o app no fim."""
        if self.installer is None or not self.installer.is_file():
            return False
        args = [str(self.installer), *INSTALL_ARGS, f"/RELAUNCH={1 if relaunch else 0}"]
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(args, creationflags=flags, close_fds=True)  # noqa: S603
        except OSError:
            log.exception("atualização: não foi possível abrir o instalador")
            return False
        log.info("atualização: instalando a versão %s", self.ready_version)
        return True
