"""Seção Foco e água: durações do pomodoro e meta, copo e lembretes da água."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aureum_island.services.storage.settings import (
    WATER_CUP_OPTIONS,
    WATER_CUP_RANGE,
    WATER_INTERVALS,
)
from aureum_island.settings.controls import (
    ChipGroup,
    NumberField,
    SettingRow,
    Switch,
    TimeField,
    body_font,
    subsection_title,
)
from aureum_island.settings.general_section import error_label, show_error
from aureum_island.settings.store import SettingsStore
from aureum_island.theme.theme import Theme
from aureum_island.theme.tokens import SETTINGS_WINDOW

_FOCUS_FIELDS = (
    ("focus_minutes", "Foco", 1, 240, " min"),
    ("short_break_minutes", "Pausa curta", 1, 240, " min"),
    ("long_break_minutes", "Pausa longa", 1, 240, " min"),
)


class FocusWaterSection(QWidget):
    def __init__(self, theme: Theme, store: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from aureum_island.settings.window import hint, section_title

        self.setAccessibleName("Foco e água")
        self.store = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_WINDOW.gap)
        layout.addWidget(section_title("Foco e água", self))

        # --- Foco ------------------------------------------------------------
        layout.addWidget(subsection_title("Foco", self))
        layout.addWidget(
            hint("Com um ciclo rodando, a nova duração vale a partir da próxima fase.", self)
        )
        self.focus_fields: dict[str, NumberField] = {}
        for key, label, low, high, suffix in _FOCUS_FIELDS:
            field = NumberField(theme, label, low, high, suffix=suffix, parent=self)
            field.valueChanged.connect(lambda v, k=key: store.update(**{k: v}))
            self.focus_fields[key] = field
            layout.addWidget(SettingRow(label, field, self))
        self.every = NumberField(theme, "Pausa longa a cada", 1, 12, suffix=" ciclos", parent=self)
        self.every.valueChanged.connect(lambda v: store.update(long_break_every=v))
        layout.addWidget(SettingRow("Pausa longa a cada", self.every, self))

        # --- Água ------------------------------------------------------------
        layout.addSpacing(SETTINGS_WINDOW.subsection_gap)
        layout.addWidget(subsection_title("Água", self))
        self.goal = NumberField(
            theme, "Meta diária", 250, 10_000, suffix=" ml", step=50, parent=self
        )
        self.goal.valueChanged.connect(lambda v: store.update(water_goal_ml=v))
        layout.addWidget(SettingRow("Meta diária", self.goal, self))

        self.cup = ChipGroup(
            theme, "Copo", tuple((ml, f"{ml} ml") for ml in WATER_CUP_OPTIONS), self
        )
        self.cup.selected.connect(lambda v: store.update(water_cup_ml=v))
        self.cup_other = NumberField(
            theme, "Outro tamanho de copo", *WATER_CUP_RANGE, suffix=" ml", step=10, parent=self
        )
        self.cup_other.valueChanged.connect(lambda v: store.update(water_cup_ml=v))
        cup_setting = SettingRow(
            "Copo", self.cup, self, hint_text="Os botões da página Água somam este valor."
        )
        cup_setting.label.setBuddy(self.cup.chips[0])
        layout.addWidget(cup_setting)
        layout.addWidget(
            SettingRow("Outro tamanho", self.cup_other, self, hint_text="De 50 a 1000 ml.")
        )

        self.reminders_switch = Switch(theme, "Lembretes de água", self)
        self.reminders_switch.clicked.connect(lambda on: store.update(water_reminders=on))
        layout.addWidget(SettingRow("Lembretes", self.reminders_switch, self))

        self.interval = ChipGroup(
            theme, "Intervalo", tuple((m, f"{m} min") for m in WATER_INTERVALS), self
        )
        self.interval.selected.connect(lambda v: store.update(water_interval_min=v))
        layout.addWidget(SettingRow("Intervalo", self.interval, self))

        self.start = TimeField(theme, "Lembretes a partir de", self)
        self.end = TimeField(theme, "Lembretes até", self)
        for field in (self.start, self.end):
            field.timeChanged.connect(lambda _t: self._save_window())
        window_controls = QWidget(self)
        window_row = QHBoxLayout(window_controls)
        window_row.setContentsMargins(0, 0, 0, 0)
        window_row.setSpacing(SETTINGS_WINDOW.chip_gap)
        until = QLabel("até", window_controls)
        until.setFont(body_font())
        window_row.addWidget(self.start)
        window_row.addWidget(until)
        window_row.addWidget(self.end)
        window_setting = SettingRow(
            "Horário dos lembretes", window_controls, self, hint_text="Fora dele, nada de aviso."
        )
        window_setting.label.setBuddy(self.start)
        layout.addWidget(window_setting)
        self.window_error = error_label(self)
        layout.addWidget(self.window_error)
        layout.addStretch(1)

        store.changed.connect(lambda _keys: self.load())
        self.load()

    def load(self) -> None:
        s = self.store.value
        for key, field in self.focus_fields.items():
            field.set_quiet(getattr(s, key))
        self.every.set_quiet(s.long_break_every)
        self.goal.set_quiet(s.water_goal_ml)
        self.cup.set_value(s.water_cup_ml)
        self.cup_other.set_quiet(s.water_cup_ml)
        self.reminders_switch.setChecked(s.water_reminders)
        self.interval.set_value(s.water_interval_min)
        if not self.window_error.isVisible():
            self.start.set_text_quiet(s.water_start)
            self.end.set_text_quiet(s.water_end)

    def _save_window(self) -> None:
        start, end = self.start.text_value(), self.end.text_value()
        if start >= end:
            show_error(self.window_error, "O início precisa ser antes do fim.")
            return
        show_error(self.window_error, "")
        self.store.update(water_start=start, water_end=end)
