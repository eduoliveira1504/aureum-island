"""--debug-paint: loga cada paintEvent do app, para conferir que o notch parado não redesenha."""

from __future__ import annotations

import logging
from collections import Counter

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

log = logging.getLogger("aureum_island.paint")

_enabled = False


def enabled() -> bool:
    return _enabled


class PaintLogger(QObject):
    """Filtro no nível da aplicação: vê o Paint de todo widget, sem código em cada um."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.counts: Counter[str] = Counter()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Paint and isinstance(watched, QWidget):
            name = watched.objectName() or type(watched).__name__
            self.counts[name] += 1
            log.info(
                "paint %s #%d (%dx%d)", name, self.counts[name], watched.width(), watched.height()
            )
        return False


def enable(app: QObject) -> PaintLogger:
    global _enabled
    _enabled = True
    logger = PaintLogger(app)
    app.installEventFilter(logger)
    return logger
