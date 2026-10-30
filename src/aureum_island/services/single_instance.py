"""Instância única: a segunda avisa a primeira (que abre o notch) e sai.

Sem isso o início automático mais um clique no atalho do app gerariam dois notches e
avisos em dobro. QLockFile decide quem é a primeira (sem corrida entre duas abrindo
juntas: no Windows dois QLocalServer podem escutar o mesmo nome); QLocalServer e
QLocalSocket levam o recado.
"""

from __future__ import annotations

import getpass
import logging
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QThread, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

MESSAGE = b"open\n"
CONNECT_TIMEOUT_MS = 1000
CONNECT_TRIES = 10  # a primeira pode estar ainda montando a UI
RETRY_MS = 200


def server_name() -> str:
    """Nome fixo por usuário do Windows (dois usuários logados não se enxergam)."""
    return f"aureum-island-{getpass.getuser()}"


class SingleInstance(QObject):
    activated = Signal()  # outra instância tentou abrir

    def __init__(self, lock_path: Path, name: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._name = name or server_name()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(lock_path))
        self._lock.setStaleLockTime(0)  # só PID morto conta como trava velha
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """True: esta é a primeira (passa a escutar). False: já existe outra."""
        if not self._lock.tryLock(0):
            return False
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not self._server.listen(self._name):
            log.warning(
                "instância única: não foi possível escutar (%s)", self._server.errorString()
            )
        self._server.newConnection.connect(self._on_connection)
        return True

    def notify(self) -> bool:
        """Na segunda instância: pede à primeira para abrir o notch."""
        for _ in range(CONNECT_TRIES):
            socket = QLocalSocket()
            socket.connectToServer(self._name)
            if socket.waitForConnected(CONNECT_TIMEOUT_MS):
                socket.write(MESSAGE)
                socket.flush()
                socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
                socket.disconnectFromServer()
                if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                    socket.waitForDisconnected(CONNECT_TIMEOUT_MS)  # termina de enviar
                return True
            QThread.msleep(RETRY_MS)
        return False

    def release(self) -> None:
        if self._server is not None:
            # Solta os sockets antes do servidor: destruir um socket ainda conectado
            # junto com o servidor derruba o processo no Windows.
            for socket in self._server.findChildren(QLocalSocket):
                socket.readyRead.disconnect()
                socket.disconnected.disconnect()
                socket.abort()
                socket.setParent(None)
                socket.deleteLater()
            self._server.close()
            self._server = None
        self._lock.unlock()

    def _on_connection(self) -> None:
        while self._server is not None and self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)
            self._read(socket)  # o recado pode já ter chegado junto com a conexão

    def _read(self, socket: QLocalSocket) -> None:
        if MESSAGE.strip() in bytes(socket.readAll()):
            self.activated.emit()
