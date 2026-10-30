"""Seção Avisos: antecedência padrão, som e notificação do Windows."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from aureum_island.island.widgets import ActionButton, ThemedSlider
from aureum_island.services.sound import Sound
from aureum_island.settings.controls import ChipGroup, SettingRow, Switch
from aureum_island.settings.store import SettingsStore
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import SETTINGS_WINDOW

OFFSET_OPTIONS = (
    (0, "Na hora"),
    (5, "5 min"),
    (10, "10 min"),
    (15, "15 min"),
    (30, "30 min"),
    (60, "1 h"),
)


class NoticesSection(QWidget):
    def __init__(
        self, theme: Theme, store: SettingsStore, sound: Sound, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import section_title

        self.setAccessibleName("Avisos")
        self.store = store

        self.offset = ChipGroup(theme, "Antecedência padrão", OFFSET_OPTIONS, self)
        self.offset.selected.connect(lambda v: store.update(reminder_offset_min=v))

        self.sound_switch = Switch(theme, "Som dos avisos", self)
        self.sound_switch.clicked.connect(lambda on: store.update(sound_enabled=on))
        self.volume = ThemedSlider(
            theme,
            track_height=SETTINGS_WINDOW.slider_track,
            handle=SETTINGS_WINDOW.slider_handle,
            window=True,
            parent=self,
        )
        self.volume.setRange(0, 100)
        self.volume.setPageStep(10)
        self.volume.setAccessibleName("Volume do som dos avisos")
        self.volume.setFixedSize(SETTINGS_WINDOW.slider_width, SETTINGS_WINDOW.slider_hit)
        # Grava ao soltar (mouse) ou a cada passo do teclado, não a cada pixel arrastado.
        self.volume.valueChanged.connect(
            lambda _v: None if self.volume.isSliderDown() else self._save_volume()
        )
        self.volume.sliderReleased.connect(self._save_volume)
        self.test_button = ActionButton("Testar som", theme, window=True, parent=self)
        self.test_button.clicked.connect(sound.preview)
        volume_controls = QWidget(self)
        volume_row = QHBoxLayout(volume_controls)
        volume_row.setContentsMargins(0, 0, 0, 0)
        volume_row.setSpacing(SETTINGS_WINDOW.gap)
        volume_row.addWidget(self.volume)
        volume_row.addWidget(self.test_button)

        self.native_switch = Switch(theme, "Notificação do Windows", self)
        self.native_switch.clicked.connect(lambda on: store.update(native_notifications=on))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(section_title("Avisos", self))
        layout.addWidget(
            SettingRow(
                "Antecedência padrão",
                self.offset,
                self,
                hint_text="Para tarefas e eventos sem antecedência própria.",
            )
        )
        layout.addWidget(SettingRow("Som", self.sound_switch, self))
        volume_setting = SettingRow("Volume", volume_controls, self)
        volume_setting.label.setBuddy(self.volume)
        layout.addWidget(volume_setting)
        layout.addWidget(
            SettingRow(
                "Notificação do Windows",
                self.native_switch,
                self,
                hint_text="Também manda cada aviso para a central de notificações.",
            )
        )
        layout.addStretch(1)

        store.changed.connect(lambda _keys: self.load())
        self.load()

    def load(self) -> None:
        s = self.store.value
        self.offset.set_value(s.reminder_offset_min)
        self.sound_switch.setChecked(s.sound_enabled)
        self.native_switch.setChecked(s.native_notifications)
        if not self.volume.isSliderDown():
            self.volume.blockSignals(True)
            self.volume.setValue(round(s.sound_volume * 100))
            self.volume.blockSignals(False)
            self.volume.update()

    def _save_volume(self) -> None:
        self.store.update(sound_volume=self.volume.value() / 100)
