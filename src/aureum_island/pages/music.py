"""Página Música: capa, faixa, progresso, controles e volume, na largura toda.

Leve: tudo chega por evento (SMTC, volume). Só com a página visível e música tocando
existe um singleShot, armado para o próximo segundo (barra e tempos).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QFontMetricsF, QImage, QPainter, QPainterPath, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from aureum_island.island import icons
from aureum_island.island.widgets import IconButton, ThemedSlider
from aureum_island.services.media import MediaService, Playback, Track
from aureum_island.services.storage.db import utc_now
from aureum_island.services.volume import VolumeService
from aureum_island.theme.fonts import make_font
from aureum_island.theme.theme import Theme, qcolor
from aureum_island.theme.tokens import COLORS, PAGES, TYPOGRAPHY

_SEEK_STEP_S = 5
_VOLUME_STEP = 5


def format_time(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def spoken_time(seconds: float | None) -> str:
    total = max(0, int(seconds or 0))
    minutes, secs = divmod(total, 60)
    return f"{minutes} min {secs} s" if minutes else f"{secs} s"


class CoverView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("music-cover")
        self.image: QImage | None = None
        self.setFixedSize(PAGES.music_cover, PAGES.music_cover)

    def set_cover(self, data: bytes | None) -> None:
        image = QImage.fromData(data) if data else None
        self.image = image if image is not None and not image.isNull() else None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        radius = PAGES.music_cover_radius
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.setClipPath(path)
        if self.image is None:
            painter.fillPath(path, qcolor(COLORS.surface))
            size = PAGES.music_cover_icon
            pm = icons.pixmap("music", COLORS.text_dim, size, self.devicePixelRatioF())
            painter.drawPixmap((self.width() - size) // 2, (self.height() - size) // 2, pm)
            return
        # Corta para quadrado (capas de vídeo são 16:9).
        img = self.image
        side = min(img.width(), img.height())
        source = QRectF((img.width() - side) / 2, (img.height() - side) / 2, side, side)
        painter.drawImage(QRectF(self.rect()), img, source)


class TrackText(QWidget):
    """Título (15/600) e artista (13), com reticências quando não cabem."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title, self.artist = "", ""
        self._title_font = make_font(
            TYPOGRAPHY.family_body, PAGES.music_title_size, PAGES.music_title_weight
        )
        self._artist_font = make_font(TYPOGRAPHY.family_body, PAGES.music_artist_size)
        height = (
            QFontMetricsF(self._title_font).height()
            + PAGES.music_title_gap
            + QFontMetricsF(self._artist_font).height()
        )
        self.setFixedHeight(round(height))

    def set_text(self, title: str, artist: str) -> None:
        if (title, artist) != (self.title, self.artist):
            self.title, self.artist = title, artist
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        width = self.width()
        tfm, afm = QFontMetricsF(self._title_font), QFontMetricsF(self._artist_font)
        painter.setFont(self._title_font)
        painter.setPen(qcolor(COLORS.text))
        title = tfm.elidedText(self.title, Qt.TextElideMode.ElideRight, width)
        painter.drawText(QRectF(0, 0, width, tfm.height()), Qt.AlignmentFlag.AlignLeft, title)
        painter.setFont(self._artist_font)
        painter.setPen(qcolor(COLORS.text_muted))
        artist = afm.elidedText(self.artist, Qt.TextElideMode.ElideRight, width)
        y = tfm.height() + PAGES.music_title_gap
        painter.drawText(QRectF(0, y, width, afm.height()), Qt.AlignmentFlag.AlignLeft, artist)


class MusicPage(QWidget):
    def __init__(
        self,
        media: MediaService,
        volume: VolumeService,
        theme: Theme,
        *,
        now: Callable[[], datetime] = utc_now,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-music")
        self.setAccessibleName("Música")
        self._media = media
        self._volume = volume
        self._theme = theme
        self._now = now
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

        self.cover = CoverView(self)
        self.text = TrackText(self)
        self.progress = ThemedSlider(
            theme, track_height=PAGES.music_progress_height, handle=0, parent=self
        )
        self.progress.setFixedHeight(PAGES.music_progress_hit)
        self.progress.setAccessibleName("Posição da faixa")
        self.progress.setSingleStep(_SEEK_STEP_S * 1000)
        self.progress.setPageStep(_SEEK_STEP_S * 1000)
        self.progress.sliderReleased.connect(self._seek_from_slider)
        self.progress.actionTriggered.connect(self._on_progress_action)
        self.elapsed = QLabel(self)
        self.total = QLabel(self)
        time_font = make_font(TYPOGRAPHY.family_body, PAGES.music_time_size, tabular=True)
        time_width = round(QFontMetricsF(time_font).horizontalAdvance("0:00:00")) + 1
        for label in (self.elapsed, self.total):
            label.setFont(time_font)
            label.setMinimumWidth(time_width)  # não corta quando o texto muda
        self.total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        c, i = PAGES.music_control, PAGES.music_icon
        self.prev = IconButton(
            "previous", "Faixa anterior", theme, size=c, icon_size=i, parent=self
        )
        self.play = IconButton(
            "play",
            "Tocar",
            theme,
            size=PAGES.music_play_button,
            icon_size=PAGES.music_play_icon,
            primary=True,
            parent=self,
        )
        self.next = IconButton("next", "Próxima faixa", theme, size=c, icon_size=i, parent=self)
        self.mute = IconButton("volume", "Silenciar", theme, size=c, icon_size=i, parent=self)
        self.volume_slider = ThemedSlider(
            theme,
            track_height=PAGES.music_progress_height,
            handle=PAGES.music_volume_handle,
            parent=self,
        )
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setSingleStep(_VOLUME_STEP)
        self.volume_slider.setPageStep(_VOLUME_STEP * 2)
        self.volume_slider.setFixedSize(PAGES.music_volume_width, PAGES.music_progress_hit)
        self.volume_slider.setAccessibleName("Volume")
        self.prev.clicked.connect(media.previous)
        self.play.clicked.connect(media.play_pause)
        self.next.clicked.connect(media.next)
        self.mute.clicked.connect(lambda: volume.set_muted(not volume.muted))
        self.volume_slider.valueChanged.connect(self._on_volume_slider)

        # Layout: capa à esquerda; faixa, progresso e controles + volume à direita.
        times = QHBoxLayout()
        times.setContentsMargins(0, 0, 0, 0)
        times.addWidget(self.elapsed)
        times.addStretch(1)
        times.addWidget(self.total)

        controls = QHBoxLayout()
        controls.setSpacing(PAGES.button_gap)
        for w in (self.prev, self.play, self.next):
            controls.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
        controls.addStretch(1)
        controls.addWidget(self.mute, 0, Qt.AlignmentFlag.AlignVCenter)
        controls.addWidget(self.volume_slider, 0, Qt.AlignmentFlag.AlignVCenter)

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addStretch(1)
        right.addWidget(self.text)
        right.addSpacing(PAGES.music_gap)
        right.addWidget(self.progress)
        right.addLayout(times)
        right.addSpacing(PAGES.button_gap)
        right.addLayout(controls)
        right.addStretch(1)

        row = QHBoxLayout(self)
        row.setContentsMargins(PAGES.music_padding_x, 0, PAGES.music_padding_x, 0)
        row.setSpacing(PAGES.music_column_gap)
        row.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(right, 1)

        for a, b in zip(
            (self.prev, self.play, self.next, self.progress, self.mute),
            (self.play, self.next, self.progress, self.mute, self.volume_slider),
            strict=True,
        ):
            QWidget.setTabOrder(a, b)

        media.track_changed.connect(self._on_track)
        media.playback_changed.connect(self._on_playback)
        media.cover_changed.connect(self.cover.set_cover)
        volume.changed.connect(self._on_volume)
        theme.changed.connect(self._apply_theme)
        self._apply_theme()
        self._on_track(media.track)
        self._on_playback(media.playback)
        self.cover.set_cover(media.cover)
        self._on_volume(volume.level, volume.muted)

    # --- visibilidade -------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        self._volume.refresh()  # pode ter trocado de fone com a página fechada
        self._refresh_position()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()

    @property
    def timer_active(self) -> bool:
        return self._timer.isActive()

    # --- faixa --------------------------------------------------------------

    def _on_track(self, track: Track | None) -> None:
        if track is None:
            self.text.set_text("Nada tocando agora", "Abra um player de música ou vídeo")
            return
        self.text.set_text(track.title, track.artist or track.album)

    # --- playback -----------------------------------------------------------

    def _on_playback(self, playback: Playback) -> None:
        has_track = self._media.track is not None
        self.prev.setEnabled(has_track and playback.can_previous)
        self.next.setEnabled(has_track and playback.can_next)
        self.play.setEnabled(has_track and playback.can_toggle)
        if playback.playing:
            self.play.set_icon("pause", "Pausar")
        else:
            self.play.set_icon("play", "Tocar")
        duration = playback.duration_s
        self.progress.setEnabled(bool(has_track and playback.can_seek))
        self.progress.setRange(0, int((duration or 0) * 1000))
        self.total.setText(format_time(duration) if has_track else "")
        self._refresh_position()

    def _refresh_position(self) -> None:
        playback = self._media.playback
        has_track = self._media.track is not None
        position = playback.position_at(self._now()) if has_track else 0.0
        if not self.progress.isSliderDown():
            self.progress.setValue(int(position * 1000))
        self.elapsed.setText(format_time(position) if has_track else "")
        self.progress.setAccessibleDescription(
            f"{spoken_time(position)} de {spoken_time(playback.duration_s)}"
        )
        self._arm(position, playback)

    def _arm(self, position: float, playback: Playback) -> None:
        """Só com a página visível e tocando: o próximo segundo."""
        if not (self.isVisible() and playback.playing and self._media.track is not None):
            self._timer.stop()
            return
        delay = 1.0 - (position % 1.0)
        self._timer.start(max(20, int(delay * 1000) + 10))

    def _tick(self) -> None:
        self._refresh_position()

    def _seek_from_slider(self) -> None:
        self._media.seek(self.progress.value() / 1000)

    def _on_progress_action(self, action: int) -> None:
        # Setas/teclado: aplica o novo valor como seek (o arrasto usa sliderReleased).
        if not self.progress.isSliderDown():
            QTimer.singleShot(0, self._seek_from_slider)

    # --- volume -------------------------------------------------------------

    def _on_volume(self, level: float, muted: bool) -> None:
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(round(level * 100))
        self.volume_slider.blockSignals(False)
        self.volume_slider.setEnabled(self._volume.available)
        self.mute.setEnabled(self._volume.available)
        if muted or level == 0:
            self.mute.set_icon("volume-mute", "Ativar som")
        else:
            self.mute.set_icon("volume", "Silenciar")
        self.volume_slider.setAccessibleDescription(f"{round(level * 100)}%")

    def _on_volume_slider(self, value: int) -> None:
        self._volume.set_level(value / 100)

    def _apply_theme(self) -> None:
        for label in (self.elapsed, self.total):
            palette = label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, qcolor(COLORS.text_muted))
            label.setPalette(palette)
