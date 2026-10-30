from datetime import UTC, datetime, timedelta

import pytest

from aureum_island.pages.music import MusicPage, format_time
from aureum_island.services.media import MediaService, Playback, Track
from aureum_island.services.volume import VolumeService
from aureum_island.theme.theme import Theme

T0 = datetime(2026, 10, 29, 20, 0, tzinfo=UTC)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


# --- posição -------------------------------------------------------------------


def test_position_interpolates_only_while_playing():
    pb = Playback(playing=True, position_s=10, updated_at=T0, duration_s=100)
    assert pb.position_at(T0 + timedelta(seconds=5)) == 15
    assert pb.position_at(T0 + timedelta(seconds=500)) == 100
    paused = Playback(playing=False, position_s=10, updated_at=T0, duration_s=100)
    assert paused.position_at(T0 + timedelta(seconds=5)) == 10


def test_format_time():
    assert format_time(0) == "0:00"
    assert format_time(65.9) == "1:05"
    assert format_time(3725) == "1:02:05"
    assert format_time(None) == "--:--"


# --- página --------------------------------------------------------------------


class FakeMedia(MediaService):
    def __init__(self):
        super().__init__()
        self.commands = []

    def play_pause(self):
        self.commands.append("toggle")

    def next(self):
        self.commands.append("next")

    def previous(self):
        self.commands.append("previous")

    def seek(self, seconds):
        self.commands.append(("seek", seconds))


@pytest.fixture
def music(qtbot):
    clock = Clock()
    media = FakeMedia()
    volume = VolumeService()
    page = MusicPage(media, volume, Theme(), now=clock)
    qtbot.addWidget(page)
    page.resize(620, 178)
    page.show()
    return type("M", (), dict(page=page, media=media, volume=volume, clock=clock))


def play(m, position=0.0, playing=True):
    m.media._apply(
        "playback",
        Playback(
            playing=playing,
            position_s=position,
            updated_at=m.clock.now,
            duration_s=200,
            can_previous=True,
            can_next=True,
            can_toggle=True,
            can_seek=True,
        ),
    )


def test_empty_state(music):
    assert music.page.text.title == "Nada tocando agora"
    assert not music.page.play.isEnabled()
    assert not music.page.timer_active


def test_track_text_and_full_width_layout(music):
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))
    assert (music.page.text.title, music.page.text.artist) == ("Canção", "Alguém")
    assert music.page.cover.size().toTuple() == (120, 120)
    assert not hasattr(music.page, "lyrics_view")
    # Coluna da direita vai até a margem: o volume fica no fim da linha dos controles.
    right_edge = music.page.volume_slider.geometry().right()
    assert music.page.width() - right_edge <= 24 + 1


def test_timer_only_when_visible_and_playing(music):
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))
    play(music, 2.0)
    assert music.page.timer_active
    assert music.page.play.accessibleName() == "Pausar"
    play(music, 2.0, playing=False)
    assert not music.page.timer_active
    assert music.page.play.accessibleName() == "Tocar"
    play(music, 2.0)
    music.page.hide()
    assert not music.page.timer_active


def test_timer_ticks_each_second(music):
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))
    play(music, 0.0)
    assert 900 <= music.page._timer.interval() <= 1100
    music.clock.now += timedelta(seconds=8.5)
    music.page._tick()
    assert music.page.elapsed.text() == "0:08"


def test_controls_and_accessibility(music):
    music.volume.set_level(0.5)
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))
    play(music)
    for button in (music.page.prev, music.page.play, music.page.next):
        button.click()
    assert music.media.commands == ["previous", "toggle", "next"]
    names = [
        w.accessibleName()
        for w in (
            music.page.prev,
            music.page.play,
            music.page.next,
            music.page.mute,
            music.page.volume_slider,
            music.page.progress,
        )
    ]
    assert names == [
        "Faixa anterior",
        "Pausar",
        "Próxima faixa",
        "Silenciar",
        "Volume",
        "Posição da faixa",
    ]


def test_volume_slider_and_mute(music):
    music.volume.available = True
    music.volume.set_level(0.5)
    assert music.page.volume_slider.value() == 50
    music.page.volume_slider.setValue(80)
    assert music.volume.level == 0.8
    music.page.mute.click()
    assert music.volume.muted
    assert music.page.mute.accessibleName() == "Ativar som"
