"""Seção Geral: início com o Windows, modo do notch, tela cheia, atalho e semana."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aureum_island.island.widgets import ActionButton
from aureum_island.services import hotkey as hotkey_service
from aureum_island.services.autostart import Autostart
from aureum_island.services.hotkey import GlobalHotkey, HotkeyStatus
from aureum_island.settings.controls import ChipGroup, HotkeyField, SettingRow, Switch
from aureum_island.settings.store import SettingsStore
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import SETTINGS_WINDOW, TYPOGRAPHY


def hotkey_status_text(hotkey: GlobalHotkey) -> str:
    text = hotkey.text or ""
    status = hotkey.status
    if status is HotkeyStatus.REGISTERED:
        return f"Ativo: {hotkey_service.display(text)}."
    if status is HotkeyStatus.FALLBACK:
        return (
            f"Ativo: {hotkey_service.display(hotkey.active or '')} "
            f"({hotkey_service.display(text)} está em uso por outro app)."
        )
    if status is HotkeyStatus.FAILED:
        return (
            f"{hotkey_service.display(text)} não está funcionando (em uso por outro app). "
            "Abra pelo ícone na bandeja ou passando o mouse no topo da tela."
        )
    if status is HotkeyStatus.UNSUPPORTED:
        return "Atalho global indisponível neste sistema."
    return "Sem atalho. Abra pelo ícone na bandeja ou passando o mouse no topo da tela."


def error_label(parent: QWidget) -> QLabel:
    label = QLabel(parent)
    label.setObjectName("error")  # cor no stylesheet da janela (danger)
    label.setWordWrap(True)
    label.setFont(make_font(TYPOGRAPHY.family_body, SETTINGS_WINDOW.hint_size))
    label.setAccessibleName("Erro")
    label.hide()
    return label


def show_error(label: QLabel, text: str) -> None:
    label.setText(text)
    label.setVisible(bool(text))


class GeneralSection(QWidget):
    def __init__(
        self,
        theme: Theme,
        store: SettingsStore,
        hotkey: GlobalHotkey,
        autostart: Autostart,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import hint, section_title

        self.setAccessibleName("Geral")
        self.store, self.hotkey, self.autostart = store, hotkey, autostart

        self.autostart_switch = Switch(theme, "Iniciar com o Windows", self)
        self.autostart_switch.clicked.connect(self._on_autostart)
        self.autostart_error = error_label(self)

        self.mode = ChipGroup(
            theme, "Modo do notch", (("normal", "Normal"), ("minimal", "Linha mínima")), self
        )
        self.mode.selected.connect(lambda v: store.update(mode=v))

        self.fullscreen_switch = Switch(theme, "Esconder em tela cheia", self)
        self.fullscreen_switch.clicked.connect(lambda on: store.update(hide_on_fullscreen=on))

        self.hotkey_field = HotkeyField(theme, self)
        self.hotkey_field.recording_changed.connect(self._on_recording)
        self.hotkey_field.captured.connect(self._change_hotkey)
        default = hotkey_service.display(hotkey_service.DEFAULT_HOTKEY)
        self.default_button = ActionButton("Usar padrão", theme, window=True, parent=self)
        self.default_button.setAccessibleName(f"Usar o atalho padrão, {default}")
        self.default_button.setToolTip(default)
        self.default_button.clicked.connect(
            lambda: self._change_hotkey(hotkey_service.DEFAULT_HOTKEY)
        )
        self.none_button = ActionButton("Sem atalho", theme, window=True, parent=self)
        self.none_button.clicked.connect(lambda: self._change_hotkey(""))
        self.hotkey_status = hint("", self)
        self.hotkey_error = error_label(self)
        hotkey_controls = QWidget(self)
        hotkey_row = QHBoxLayout(hotkey_controls)
        hotkey_row.setContentsMargins(0, 0, 0, 0)
        hotkey_row.setSpacing(SETTINGS_WINDOW.chip_gap)
        for widget in (self.hotkey_field, self.default_button, self.none_button):
            hotkey_row.addWidget(widget)

        self.week = ChipGroup(
            theme, "Início da semana", (("sunday", "Domingo"), ("monday", "Segunda")), self
        )
        self.week.selected.connect(lambda v: store.update(week_start=v))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(section_title("Geral", self))
        layout.addWidget(
            SettingRow(
                "Iniciar com o Windows",
                self.autostart_switch,
                self,
                hint_text="Abre o Aureum Island quando você entra no Windows.",
            )
        )
        layout.addWidget(self.autostart_error)
        layout.addWidget(
            SettingRow(
                "Modo do notch",
                self.mode,
                self,
                hint_text="Linha mínima: uma linha fina no topo, para telas com borda grossa.",
            )
        )
        layout.addWidget(
            SettingRow(
                "Esconder em tela cheia",
                self.fullscreen_switch,
                self,
                hint_text="Some durante jogos, vídeos e apresentações. Os avisos esperam.",
            )
        )
        hotkey_setting = SettingRow("Atalho global", hotkey_controls, self)
        hotkey_setting.label.setBuddy(self.hotkey_field)
        layout.addWidget(hotkey_setting)
        layout.addWidget(self.hotkey_status)
        layout.addWidget(self.hotkey_error)
        layout.addWidget(SettingRow("Início da semana", self.week, self))
        layout.addStretch(1)

        store.changed.connect(lambda _keys: self.load())
        hotkey.status_changed.connect(self._show_hotkey)
        self.load()

    def load(self) -> None:
        s = self.store.value
        self.autostart_switch.setChecked(s.autostart)
        self.mode.set_value(s.mode)
        self.fullscreen_switch.setChecked(s.hide_on_fullscreen)
        self.week.set_value(s.week_start)
        self._show_hotkey()

    def _show_hotkey(self) -> None:
        self.hotkey_field.set_hotkey(self.hotkey.text or "")
        self.hotkey_status.setText(hotkey_status_text(self.hotkey))
        self.hotkey_status.setAccessibleName(self.hotkey_status.text())

    def _on_autostart(self, on: bool) -> None:
        if self.autostart.set_enabled(on):
            show_error(self.autostart_error, "")
            self.store.update(autostart=on)
        else:
            self.autostart_switch.setChecked(not on)
            show_error(self.autostart_error, "Não foi possível alterar o registro do Windows.")

    def _on_recording(self, recording: bool) -> None:
        # Enquanto grava, o atalho atual fica solto para a combinação chegar ao campo.
        if recording:
            self.hotkey.suspend()
        else:
            self.hotkey.resume()

    def _change_hotkey(self, text: str) -> None:
        reason = self.hotkey.change(text)
        if reason is not None:
            show_error(self.hotkey_error, reason)
            self._show_hotkey()
            return
        show_error(self.hotkey_error, "")
        self.store.update(hotkey=text)
        self._show_hotkey()
