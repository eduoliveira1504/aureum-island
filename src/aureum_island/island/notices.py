"""Avisos no notch: o conteúdo (NoticeView) e a fila (NoticeCenter).

Um aviso por vez. Se o notch estiver aberto, espera ele fechar; em tela cheia, espera
sem som e, se juntar 2 ou mais, vira um único "N avisos perdidos". O tempo de 8 s pausa
com o mouse em cima (ou com o aviso focado pelo teclado).
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetricsF, QPainter
from PySide6.QtWidgets import QHBoxLayout, QWidget

from aureum_island.island import icons
from aureum_island.island.state import State
from aureum_island.island.widgets import ActionButton
from aureum_island.theme import color
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import NOTICE, PAGES, TYPOGRAPHY

log = logging.getLogger(__name__)


@dataclass
class NoticeAction:
    label: str
    run: Callable[[], None]
    primary: bool = False


@dataclass
class Notice:
    title: str
    subtitle: str
    icon: str
    actions: list[NoticeAction] = field(default_factory=list)
    kind: str = ""
    count: int = 1  # quantos avisos este representa (para juntar em "N perdidos")
    sound_pending: bool = False
    # False: lembrete que perde o sentido se atrasar (água). Não conta em "N avisos
    # perdidos"; ao sair da tela cheia, só o mais recente aparece.
    stale_ok: bool = True

    @property
    def primary(self) -> NoticeAction | None:
        return next(
            (a for a in self.actions if a.primary), self.actions[0] if self.actions else None
        )


def missed_summary(count: int, subtitle: str, see: Callable[[], None]) -> Notice:
    return Notice(
        title=f"{count} avisos perdidos",
        subtitle=subtitle,
        icon="bell",
        actions=[NoticeAction("Ver", see, primary=True)],
        kind="missed",
        count=count,
    )


def collapse_missed(
    notices: Sequence[Notice], subtitle: str, see: Callable[[], None]
) -> list[Notice]:
    """0 ou 1 aviso: como está. 2 ou mais: um único "N avisos perdidos" com "Ver"."""
    if len(notices) < 2:
        return list(notices)
    return [missed_summary(sum(n.count for n in notices), subtitle, see)]


# --- vista -------------------------------------------------------------------


class NoticeView(QWidget):
    """360x64: círculo com ícone, título + subtítulo, botões de 30 px à direita."""

    action_triggered = Signal(object)  # NoticeAction
    dismiss_requested = Signal()

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("notice")
        self._theme = theme
        self.notice: Notice | None = None
        self.buttons: list[ActionButton] = []
        self._title_font = make_font(TYPOGRAPHY.family_body, NOTICE.title_size, NOTICE.title_weight)
        self._subtitle_font = make_font(TYPOGRAPHY.family_body, NOTICE.subtitle_size, tabular=True)
        self.setFixedSize(NOTICE.width, NOTICE.height)
        self._row = QHBoxLayout(self)
        left = NOTICE.padding_x + NOTICE.icon + NOTICE.gap
        self._row.setContentsMargins(left, 0, NOTICE.padding_x, 0)
        self._row.setSpacing(PAGES.button_gap)
        self._row.addStretch(1)
        theme.changed.connect(self.update)

    def set_notice(self, notice: Notice) -> None:
        self.notice = notice
        for button in self.buttons:
            self._row.removeWidget(button)
            button.deleteLater()
        self.buttons = []
        for action in notice.actions:
            button = ActionButton(action.label, self._theme, primary=action.primary, parent=self)
            button.clicked.connect(lambda _=False, a=action: self.action_triggered.emit(a))
            self._row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
            self.buttons.append(button)
        # Ordem de Tab: principal primeiro.
        ordered = sorted(self.buttons, key=lambda b: not b.primary)
        for a, b in zip(ordered, ordered[1:], strict=False):
            QWidget.setTabOrder(a, b)
        self.setAccessibleName(f"{notice.title}. {notice.subtitle}")
        self.update()

    def focus_primary(self) -> None:
        for button in self.buttons:
            if button.primary:
                button.setFocus(Qt.FocusReason.TabFocusReason)
                return
        if self.buttons:
            self.buttons[0].setFocus(Qt.FocusReason.TabFocusReason)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.notice is not None:
            focused = next((b for b in self.buttons if b.hasFocus()), None)
            if focused is not None:
                focused.click()
            elif self.notice.primary is not None:
                self.action_triggered.emit(self.notice.primary)
            return
        if key == Qt.Key.Key_Escape:
            self.dismiss_requested.emit()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        if self.notice is None:
            return
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size, h = NOTICE.icon, self.height()
        top = (h - size) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(color.with_alpha(theme.accent, NOTICE.icon_bg_alpha)))
        painter.drawEllipse(QRectF(NOTICE.padding_x, top, size, size))
        glyph = NOTICE.icon_glyph
        pm = icons.pixmap(self.notice.icon, theme.accent_text, glyph, self.devicePixelRatioF())
        offset = (size - glyph) / 2
        painter.drawPixmap(int(NOTICE.padding_x + offset), int(top + offset), pm)

        x = NOTICE.padding_x + size + NOTICE.gap
        right = self.buttons[0].x() if self.buttons else self.width() - NOTICE.padding_x
        width = max(0, right - NOTICE.gap - x)
        title_fm, sub_fm = QFontMetricsF(self._title_font), QFontMetricsF(self._subtitle_font)
        block = title_fm.height() + sub_fm.height()
        y = (h - block) / 2
        painter.setFont(self._title_font)
        painter.setPen(qcolor(self._theme.notch.text))
        title = title_fm.elidedText(self.notice.title, Qt.TextElideMode.ElideRight, width)
        painter.drawText(QRectF(x, y, width, title_fm.height()), Qt.AlignmentFlag.AlignLeft, title)
        painter.setFont(self._subtitle_font)
        painter.setPen(qcolor(self._theme.notch.text_muted))
        sub = sub_fm.elidedText(self.notice.subtitle, Qt.TextElideMode.ElideRight, width)
        sub_rect = QRectF(x, y + title_fm.height(), width, sub_fm.height())
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft, sub)


# --- fila --------------------------------------------------------------------


class NoticeCenter(QObject):
    shown = Signal(object)  # Notice

    def __init__(
        self,
        controller,
        *,
        play_sound: Callable[[], None],
        native: Callable[[Notice], None] | None = None,
        open_tasks: Callable[[], None] = lambda: None,
        duration_ms: int = NOTICE.duration_ms,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._play = play_sound
        self._native = native
        self._open_tasks = open_tasks
        self._duration = duration_ms
        self.queue: deque[Notice] = deque()
        self.current: Notice | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._remaining: int | None = None  # pausado (mouse em cima / foco)
        self._hovering = False
        self._focused = False

        view = controller.notch.notice_view
        view.action_triggered.connect(self.trigger)
        view.dismiss_requested.connect(self.dismiss)
        controller.machine.add_listener(self._on_state)
        controller.hover_changed.connect(self._on_hover)
        controller.suppressed_changed.connect(self._on_suppressed)
        controller.notice_focus_changed.connect(self._on_focus)

    # --- entrada ------------------------------------------------------------

    def push(self, notice: Notice) -> None:
        if self._native is not None:
            self._native(notice)  # o Windows segura no "não perturbe"
        if self._ctrl.suppressed:
            notice.sound_pending = True
            self.queue.append(notice)
            return
        self._play()
        self.queue.append(notice)
        self._show_next()

    def push_many(self, notices: Sequence[Notice]) -> None:
        for notice in notices:
            self.push(notice)

    # --- ações --------------------------------------------------------------

    def trigger(self, action: NoticeAction) -> None:
        self._finish()
        action.run()
        if self._ctrl.machine.state is State.NOTICE:
            self._ctrl.dismiss_notice()

    def dismiss(self) -> None:
        self._finish()
        self._ctrl.dismiss_notice()

    @property
    def remaining_ms(self) -> int | None:
        if self._timer.isActive():
            return self._timer.remainingTime()
        return self._remaining

    # --- interno ------------------------------------------------------------

    def _finish(self) -> None:
        self._timer.stop()
        self._remaining = None
        self.current = None

    def _show_next(self) -> None:
        if self.current is not None or not self.queue or self._ctrl.suppressed:
            return
        if not self._ctrl.machine.at_rest:
            return  # notch aberto: espera fechar
        notice = self.queue.popleft()
        if notice.sound_pending:
            notice.sound_pending = False
            self._play()
        if not self._ctrl.present_notice(notice):
            self.queue.appendleft(notice)
            return
        self.current = notice
        self._hovering = self._focused = False
        self._remaining = None
        self._timer.start(self._duration)
        self.shown.emit(notice)

    def _on_state(self, old: State, new: State, reason: str) -> None:
        if old is State.NOTICE and new is not State.NOTICE and self.current is not None:
            # Saiu do aviso por outro caminho (ex.: tela cheia): devolve à fila.
            self.queue.appendleft(self.current)
            self._finish()
        if new in (State.CLOSED, State.MINIMAL):
            # Deixa a animação de fechar terminar o tick atual antes do próximo aviso.
            QTimer.singleShot(0, self._show_next)

    def _on_hover(self, inside: bool) -> None:
        self._hovering = inside
        self._update_pause()

    def _on_focus(self, focused: bool) -> None:
        self._focused = focused
        self._update_pause()

    def _update_pause(self) -> None:
        if self.current is None:
            return
        paused = self._hovering or self._focused
        if paused and self._timer.isActive():
            self._remaining = self._timer.remainingTime()
            self._timer.stop()
        elif not paused and not self._timer.isActive() and self._remaining is not None:
            self._timer.start(self._remaining)
            self._remaining = None

    def _on_suppressed(self, suppressed: bool) -> None:
        if suppressed:
            return
        if len(self.queue) >= 2:
            fresh = [n for n in self.queue if n.stale_ok]
            perishable = [n for n in self.queue if not n.stale_ok][-1:]
            merged = collapse_missed(fresh, "Durante a tela cheia", self._open_tasks)
            for notice in merged + perishable:
                notice.sound_pending = True
            self.queue = deque(merged + perishable)
        self._show_next()
