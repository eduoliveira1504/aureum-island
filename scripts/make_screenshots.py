"""Prints do app para a página (site/img), em 2880x1800.

    .venv\\Scripts\\python scripts\\make_screenshots.py site\\img

Roda o app de verdade, num processo à parte para cada print, com uma pasta de dados de
demonstração (tarefas, eventos e água fictícios, sem agenda ICS) e escala 300%. Captura
as janelas do notch e da sombra com grab() e cola sobre um fundo neutro gerado aqui, sem
nada da área de trabalho real.

- Música mostra o que estiver tocando no Windows: antes, toque a faixa fictícia de
  scripts/make_demo_track.py no Media Player.
- Os outros prints fixam o relógio em 15:20 de hoje, só dentro do processo do print.
"""

from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ("musica", "foco", "agua", "tarefas", "calendario", "avisos")
SCALE = 3
CANVAS = (2880, 1800)
FAKE_TIME = (15, 20)


# --- relógio fixo (antes de importar o app) ---------------------------------------


def _freeze_clock(hour: int, minute: int) -> list[_dt.timedelta]:
    """Troca datetime.datetime e datetime.date por versões cujo 'agora' anda a partir de
    hoje às hour:minute. Devolve uma lista com o deslocamento extra (mutável) para voltar
    no tempo ao criar dados."""
    real_datetime, real_date = _dt.datetime, _dt.date
    real_now = real_datetime.now().astimezone()
    target = real_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    base = target - real_now
    extra = [_dt.timedelta(0)]

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            moment = real_datetime.now(tz) + base + extra[0]
            return cls.fromtimestamp(moment.timestamp(), tz)

    class FrozenDate(real_date):
        @classmethod
        def today(cls):
            day = FrozenDateTime.now().date()
            return cls(day.year, day.month, day.day)

    _dt.datetime = FrozenDateTime
    _dt.date = FrozenDate
    return extra


# --- um print (processo filho) ------------------------------------------------------


def _seed(island, shot: str, extra: list[_dt.timedelta]) -> None:
    from datetime import datetime, timedelta

    local = datetime.now().astimezone()

    def at(hour: int, minute: int, days: int = 0) -> datetime:
        return local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(
            days=days
        )

    tasks = island.tasks
    done = tasks.add("Revisar os slides da apresentação", at(11, 0))
    tasks.set_done(done.id)
    tasks.add("Enviar a proposta do projeto", at(16, 0))
    tasks.add("Alongar 5 minutos", at(17, 30))
    tasks.add("Pagar a conta de luz", at(18, 0))
    tasks.add("Comprar café")

    events = island.calendar_events
    events.add_local("Reunião de alinhamento", at(16, 30), at(17, 0))
    events.add_local("Academia", at(19, 0), at(20, 0))
    for days, title, hour in (
        (-9, "Dentista", 10),
        (-3, "Aniversário da Lia", 20),
        (1, "Feira de sábado", 9),
        (4, "Entrega do relatório", 14),
        (11, "Show à noite", 21),
    ):
        events.add_local(title, at(hour, 0, days), at(hour + 1, 0, days))

    water = island.water
    real_now = water._now
    for hour, minute, ml in (
        (8, 10, 250),
        (9, 40, 250),
        (11, 5, 300),
        (12, 45, 250),
        (14, 20, 250),
    ):
        water._now = lambda h=hour, m=minute: at(h, m).astimezone(_dt.UTC)
        water.add(ml)
    water._now = real_now

    if shot == "foco":
        extra[0] = timedelta(minutes=-8, seconds=-24)  # começou há 8 min
        island.focus.start()
        extra[0] = timedelta(0)


def _run_one(shot: str, out: Path) -> int:
    os.environ["QT_SCALE_FACTOR"] = str(SCALE)
    extra = _freeze_clock(*FAKE_TIME) if shot != "musica" else [_dt.timedelta(0)]

    sys.path.insert(0, str(ROOT / "src"))
    from PySide6.QtCore import QPoint, QPointF, QRect, QTimer
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QRadialGradient
    from PySide6.QtWidgets import QApplication

    from aureum_island.island.notices import Notice, NoticeAction
    from aureum_island.pages.water import format_ml
    from aureum_island.services.storage import paths
    from aureum_island.theme.fonts import register_fonts

    app = QApplication([])
    app.setApplicationName(paths.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    register_fonts()
    from aureum_island.app import AureumIsland

    island = AureumIsland(app)
    _seed(island, shot, extra)
    island.start()
    island.tray.hide()
    ctrl = island.controller

    def stage() -> None:
        if shot == "avisos":
            # O mesmo aviso que o app monta para a água (app._notice_for).
            total = format_ml(island.water.total_today())
            goal = format_ml(island.settings.water_goal_ml)
            cup = island.settings.water_cup_ml
            island.notices.push(
                Notice(
                    title="Hora de beber água",
                    subtitle=f"Hoje: {total} de {goal} ml",
                    icon="water",
                    kind="water",
                    actions=[NoticeAction(f"+{cup} ml", lambda: None, primary=True)],
                )
            )
        else:
            page = {
                "musica": "music",
                "foco": "focus",
                "agua": "water",
                "tarefas": "tasks",
                "calendario": "calendar",
            }[shot]
            ctrl.open_page(page)

    def capture() -> None:
        screen = ctrl.notch.screen().geometry()
        image = QImage(*CANVAS, QImage.Format.Format_RGB32)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        _wallpaper(p, QRect(0, 0, *CANVAS), QColor, QLinearGradient, QRadialGradient, QPointF)
        # A tela lógica do print tem CANVAS / SCALE; o notch fica no centro do topo.
        dx = (CANVAS[0] / SCALE - screen.width()) / 2 - screen.x()
        for window in (ctrl.shadow, ctrl.notch):
            if not window.isVisible():
                continue
            shot_pm = window.grab()
            shot_pm.setDevicePixelRatio(1)  # já vem em pixels físicos (SCALE x)
            pos = window.geometry().topLeft()
            target = QPoint(round((pos.x() + dx) * SCALE), round((pos.y() - screen.y()) * SCALE))
            p.drawPixmap(target, shot_pm)
        p.end()
        image.save(str(out), "PNG")
        print(f"{out.name}: {image.width()}x{image.height()}")
        app.quit()

    QTimer.singleShot(1500, stage)
    QTimer.singleShot(4000, capture)
    return app.exec()


def _wallpaper(p, rect, QColor, QLinearGradient, QRadialGradient, QPointF) -> None:  # noqa: N803
    """Fundo neutro: degradê frio para quente com dois brilhos suaves."""
    w, h = rect.width(), rect.height()
    base = QLinearGradient(QPointF(0, 0), QPointF(w, h))
    base.setColorAt(0.0, QColor("#2E3A46"))
    base.setColorAt(0.55, QColor("#5E6E78"))
    base.setColorAt(1.0, QColor("#A89780"))
    p.fillRect(rect, base)
    for cx, cy, radius, color in (
        (0.18, 0.85, 0.55, QColor(120, 150, 170, 90)),
        (0.85, 0.2, 0.5, QColor(200, 170, 130, 70)),
    ):
        glow = QRadialGradient(QPointF(w * cx, h * cy), w * radius)
        glow.setColorAt(0, color)
        transparent = QColor(color)
        transparent.setAlpha(0)
        glow.setColorAt(1, transparent)
        p.fillRect(rect, glow)


# --- orquestra ------------------------------------------------------------------------


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--one":
        return _run_one(sys.argv[2], Path(sys.argv[3]))
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    for shot in SHOTS:
        with tempfile.TemporaryDirectory(prefix="aureum-island-demo-") as data:
            Path(data, "settings.json").write_text(
                '{"sound_enabled": false, "water_reminders": false, '
                '"hide_on_fullscreen": false, "hotkey": ""}',
                encoding="utf-8",
            )
            env = dict(os.environ, AUREUM_ISLAND_DATA_DIR=data)
            subprocess.run(
                [sys.executable, __file__, "--one", shot, str(out_dir / f"{shot}.png")],
                check=True,
                env=env,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
