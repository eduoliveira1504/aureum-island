"""Seção Calendário das Configurações: agendas ICS (nome, cor, link, atualizar, remover).

O link vai para o cofre do Windows ao salvar. Na lista aparece só o domínio.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from aureum_island.island.widgets import ActionButton, line_edit_style
from aureum_island.services.calendar_sync import CalendarSync, Source, status_text
from aureum_island.services.ics import InvalidLink
from aureum_island.services.storage.secrets import SecretStoreError
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import ACCENT_PRESETS, COLORS, NOTCH, SETTINGS_WINDOW, TYPOGRAPHY


class ColorSwatch(QAbstractButton):
    def __init__(self, name: str, hex_color: str, theme: Theme, parent: QWidget) -> None:
        super().__init__(parent)
        self.hex = hex_color
        self._theme = theme
        self.setCheckable(True)
        self.setFixedSize(SETTINGS_WINDOW.color_swatch + 6, SETTINGS_WINDOW.color_swatch + 6)
        self.setAccessibleName(f"Cor {name}")
        self.setToolTip(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = SETTINGS_WINDOW.color_swatch
        rect = QRectF(3, 3, s, s)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(self.hex))
        painter.drawEllipse(rect)
        if self.isChecked() or self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcolor(COLORS.text), NOTCH.focus_ring_width))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))


class SourceRow(QWidget):
    def __init__(self, section: CalendarSection, source: Source) -> None:
        super().__init__(section)
        self.source = source
        self._section = section
        self.setFixedHeight(SETTINGS_WINDOW.list_row_height)
        self._name_font = make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.body_size, 600)
        self._info_font = make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.hint_size)
        self.info = ""
        theme = section.theme
        self.refresh_button = ActionButton("Atualizar", theme, parent=self)
        self.refresh_button.setAccessibleName(f"Atualizar {source.name}")
        self.remove_button = ActionButton("Remover", theme, parent=self)
        self.remove_button.setAccessibleName(f"Remover {source.name}")
        self.refresh_button.clicked.connect(lambda: section.sync.sync(source.id))
        self.remove_button.clicked.connect(self._remove)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addStretch(1)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.remove_button)
        self._confirming = False

    def set_info(self, domain: str, status: str) -> None:
        self.info = f"{domain} · {status}" if domain else status
        self.setAccessibleName(f"{self.source.name}, {self.info}")
        self.update()

    def _remove(self) -> None:
        # Dois cliques: o primeiro pede confirmação no próprio botão.
        if not self._confirming:
            self._confirming = True
            self.remove_button.setText("Confirmar remoção")
            self.remove_button.setAccessibleName(f"Confirmar remoção de {self.source.name}")
            return
        self._section.sync.remove_source(self.source.id)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dot = SETTINGS_WINDOW.list_dot
        h = self.height()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor(self.source.color))
        painter.drawEllipse(QRectF(0, h / 2 - dot / 2, dot, dot))
        x = dot + SETTINGS_WINDOW.gap
        width = max(0, self.refresh_button.x() - SETTINGS_WINDOW.gap - x)
        nfm, ifm = QFontMetricsF(self._name_font), QFontMetricsF(self._info_font)
        y = (h - nfm.height() - ifm.height()) / 2
        painter.setFont(self._name_font)
        painter.setPen(qcolor(COLORS.text))
        name = nfm.elidedText(self.source.name, Qt.TextElideMode.ElideRight, width)
        painter.drawText(QRectF(x, y, width, nfm.height()), Qt.AlignmentFlag.AlignLeft, name)
        painter.setFont(self._info_font)
        failed = self.source.last_status == "failed"
        painter.setPen(qcolor(COLORS.danger_text if failed else COLORS.text_muted))
        info = ifm.elidedText(self.info, Qt.TextElideMode.ElideRight, width)
        painter.drawText(
            QRectF(x, y + nfm.height(), width, ifm.height()), Qt.AlignmentFlag.AlignLeft, info
        )


class CalendarSection(QWidget):
    def __init__(self, theme: Theme, sync: CalendarSync, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import hint, section_title

        self.setAccessibleName("Calendário")
        self.theme = theme
        self.sync = sync
        self.rows: list[SourceRow] = []

        body = make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.body_size)
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Ex.: Trabalho")
        self.name_input.setAccessibleName("Nome da agenda")
        self.link_input = QLineEdit(self)
        self.link_input.setPlaceholderText("https://… ou webcal://…")
        self.link_input.setAccessibleName("Link ICS secreto")
        self.link_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.link_input.setToolTip("O link fica guardado no cofre do Windows.")
        for field in (self.name_input, self.link_input):
            field.setFont(body)
            field.setFixedHeight(SETTINGS_WINDOW.input_height)
            field.returnPressed.connect(self.add)

        swatches = QWidget(self)
        swatch_row = QHBoxLayout(swatches)
        swatch_row.setContentsMargins(0, 0, 0, 0)
        swatch_row.setSpacing(SETTINGS_WINDOW.gap // 2)
        self.colors = QButtonGroup(self)
        self.colors.setExclusive(True)
        for i, (name, hex_color) in enumerate(ACCENT_PRESETS.values()):
            swatch = ColorSwatch(name, hex_color, theme, swatches)
            self.colors.addButton(swatch, i)
            swatch_row.addWidget(swatch)
        swatch_row.addStretch(1)
        self.colors.button(1).setChecked(True)  # Ametista: distingue do accent padrão

        self.add_button = ActionButton("Adicionar agenda", theme, primary=True, parent=self)
        self.add_button.clicked.connect(self.add)
        self.error = QLabel(self)
        self.error.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.hint_size))
        self.error.setObjectName("error")  # cor no stylesheet da janela (danger)
        self.error.setAccessibleName("Erro")

        form = QGridLayout()
        form.setHorizontalSpacing(SETTINGS_WINDOW.gap)
        form.setVerticalSpacing(SETTINGS_WINDOW.gap)
        for row, (label_text, widget) in enumerate(
            (("Nome", self.name_input), ("Cor", swatches), ("Link", self.link_input))
        ):
            label = QLabel(label_text, self)
            label.setFont(body)
            if isinstance(widget, QLineEdit):
                label.setBuddy(widget)
            form.addWidget(label, row, 0)
            form.addWidget(widget, row, 1)
        actions = QHBoxLayout()
        actions.addWidget(self.add_button)
        actions.addWidget(self.error, 1)
        form.addLayout(actions, 3, 1)
        form.setColumnStretch(1, 1)

        self.list_title = QLabel("Suas agendas", self)
        self.list_title.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.body_size, 600))
        self.empty = hint("Nenhuma agenda ainda.", self)
        self._list = QVBoxLayout()
        self._list.setSpacing(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(section_title("Calendário", self))
        layout.addWidget(
            hint(
                "Cole o link ICS secreto da sua agenda (Google: Configurações da agenda → "
                "Endereço secreto no formato iCal; Outlook: Publicar agenda → ICS). Ele dá "
                "acesso à agenda inteira, então fica guardado no cofre do Windows e nunca "
                "aparece aqui de novo.",
                self,
            )
        )
        layout.addLayout(form)
        layout.addSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(self.list_title)
        layout.addWidget(self.empty)
        layout.addLayout(self._list)
        layout.addStretch(1)

        sync.sources_changed.connect(self.refresh)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self.refresh()

    def add(self) -> None:
        color = self.colors.checkedButton().hex
        try:
            self.sync.add_source(self.name_input.text(), color, self.link_input.text())
        except InvalidLink as exc:
            self.error.setText(str(exc))
            self.link_input.setStyleSheet(line_edit_style(self.theme, error=True))
            self.link_input.setFocus()
            return
        except SecretStoreError:
            self.error.setText("Não foi possível guardar o link no cofre do Windows.")
            return
        self.error.clear()
        self.name_input.clear()
        self.link_input.clear()
        self._apply_theme()

    def refresh(self) -> None:
        for row in self.rows:
            self._list.removeWidget(row)
            row.deleteLater()
        self.rows = []
        for source in self.sync.sources():
            row = SourceRow(self, source)
            row.set_info(
                self.sync.domain_of(source.id), status_text(source, source.id in self.sync.syncing)
            )
            self._list.addWidget(row)
            self.rows.append(row)
        self.empty.setVisible(not self.rows)

    def _apply_theme(self) -> None:
        for field in (self.name_input, self.link_input):
            field.setStyleSheet(line_edit_style(self.theme))
