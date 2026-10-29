from datetime import UTC, datetime, timedelta

import pytest

from aureum_island.pages.lyrics_model import (
    LyricLine,
    Lyrics,
    cache_key,
    current_index,
    next_change_s,
    parse_lrc,
)
from aureum_island.pages.music import MusicPage, format_time
from aureum_island.services.lyrics import (
    LyricsCache,
    LyricsService,
    from_record,
    pick_best,
    user_agent,
)
from aureum_island.services.media import MediaService, Playback, Track
from aureum_island.services.storage import db
from aureum_island.services.volume import VolumeService
from aureum_island.theme.theme import Theme

T0 = datetime(2026, 10, 29, 20, 0, tzinfo=UTC)

LRC = """[ar:Alguém]
[ti:Canção]
[00:01.50]Primeira
[00:04.00][00:20.00]Refrão
[00:08.25]Terceira
"""


# --- LRC ---------------------------------------------------------------------


def test_parse_lrc_multiple_stamps_and_tags():
    lines = parse_lrc(LRC)
    assert lines == [
        LyricLine(1.5, "Primeira"),
        LyricLine(4.0, "Refrão"),
        LyricLine(8.25, "Terceira"),
        LyricLine(20.0, "Refrão"),
    ]


def test_parse_lrc_offset_and_centiseconds():
    lines = parse_lrc("[offset:+500]\n[01:02.5]A\n[00:00.10]B")
    assert lines == [LyricLine(0.0, "B"), LyricLine(62.0, "A")]  # +500 ms adianta


def test_current_line_and_next_change():
    lyrics = Lyrics.synced(parse_lrc(LRC))
    assert current_index(lyrics, 0.5) == -1
    assert current_index(lyrics, 1.5) == 0
    assert current_index(lyrics, 7.9) == 1
    assert current_index(lyrics, 30) == 3
    assert next_change_s(lyrics, 2.0) == 2.0
    assert next_change_s(lyrics, 25) is None


def test_cache_key_normalizes_and_ignores_duration():
    assert cache_key("  The  Band ", "SONG", "Álbum") == cache_key("the band", "song", "álbum")


# --- respostas do LRCLIB -----------------------------------------------------


def test_from_record_variants():
    assert from_record({"syncedLyrics": "[00:01.00]Oi", "plainLyrics": "Oi"})[0].status == "synced"
    plain, content = from_record({"syncedLyrics": None, "plainLyrics": " Oi\nTchau "})
    assert (plain.status, plain.plain, content) == ("plain", "Oi\nTchau", "Oi\nTchau")
    assert from_record({"instrumental": True})[0].status == "instrumental"
    assert from_record({})[0].status == "not_found"
    assert from_record(None)[0].status == "not_found"


def test_pick_best_prefers_synced_with_matching_duration():
    results = [
        {"id": 1, "duration": 200, "plainLyrics": "a"},
        {"id": 2, "duration": 260, "syncedLyrics": "[00:01.00]x"},
        {"id": 3, "duration": 201, "syncedLyrics": "[00:01.00]y"},
    ]
    assert pick_best(results, 200.4)["id"] == 3
    assert pick_best(results, None)["id"] == 2
    assert pick_best([], 200) is None
    assert pick_best({"erro": 1}, 200) is None


def test_user_agent():
    assert user_agent().startswith("AureumIsland/")
    assert user_agent().endswith("(https://github.com/eduoliveira1504/aureum-island)")


# --- cache ---------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "data.db")
    yield c
    c.close()


def test_found_lyrics_never_expire(conn):
    clock = Clock()
    cache = LyricsCache(conn, now=clock)
    cache.put("k", Lyrics("plain", plain="oi"), "oi")
    clock.now += timedelta(days=400)
    assert cache.get("k").plain == "oi"


def test_not_found_expires_after_7_days(conn):
    clock = Clock()
    cache = LyricsCache(conn, now=clock)
    cache.put("k", Lyrics("not_found"), "")
    clock.now += timedelta(days=6)
    assert cache.get("k").status == "not_found"
    clock.now += timedelta(days=2)
    assert cache.get("k") is None


def test_lru_eviction_by_size(conn):
    clock = Clock()
    cache = LyricsCache(conn, now=clock, max_bytes=250)
    for name in ("a", "b", "c"):
        cache.put(name, Lyrics("plain", plain="x"), "x" * 100)
        clock.now += timedelta(minutes=1)
    # "a" foi a primeira; "b" é usada agora, então "a" e depois "c" são as menos usadas.
    assert cache.get("a") is None
    cache.get("b")
    clock.now += timedelta(minutes=1)
    cache.put("d", Lyrics("plain", plain="x"), "x" * 100)
    assert cache.get("c") is None
    assert cache.get("b") is not None
    assert cache.get("d") is not None
    assert cache.total_bytes() <= 250


# --- serviço com rede falsa ---------------------------------------------------


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses  # path -> (status, body)
        self.calls = []

    def get(self, url, params, callback):
        path = url.rsplit("/api", 1)[1]
        self.calls.append((path, dict(params)))
        status, body = self.responses.get(path, (404, None))
        callback(status, body)


def service(conn, http, enabled=True):
    s = LyricsService(conn, http=http, enabled=lambda: enabled)
    got = []
    s.ready.connect(lambda key, lyrics: got.append(lyrics))
    return s, got


def test_get_then_cached(qapp, conn):
    http = FakeHttp({"/get": (200, {"syncedLyrics": "[00:01.00]Oi"})})
    s, got = service(conn, http)
    s.request("Artista", "Faixa", "Álbum", 201.7)
    assert http.calls == [
        (
            "/get",
            {
                "artist_name": "Artista",
                "track_name": "Faixa",
                "album_name": "Álbum",
                "duration": "202",
            },
        )
    ]
    s.request("Artista", "Faixa", "Álbum", None)  # mesma faixa: cache, sem rede
    assert len(http.calls) == 1
    assert [g.status for g in got] == ["synced", "synced"]


def test_get_404_falls_back_to_search(qapp, conn):
    http = FakeHttp(
        {"/get": (404, None), "/search": (200, [{"duration": 200, "plainLyrics": "Letra"}])}
    )
    s, got = service(conn, http)
    s.request("Artista", "Faixa", "Álbum", 200)
    assert [c[0] for c in http.calls] == ["/get", "/search"]
    assert got[0].status == "plain"


def test_missing_album_goes_straight_to_search(qapp, conn):
    http = FakeHttp({"/search": (200, [])})
    s, got = service(conn, http)
    s.request("Artista", "Faixa", "", None)
    assert [c[0] for c in http.calls] == ["/search"]
    assert got[0].status == "not_found"
    s.request("Artista", "Faixa", "", None)
    assert len(http.calls) == 1  # "não encontrada" em cache


def test_network_error_is_not_cached(qapp, conn):
    http = FakeHttp({"/get": (None, None)})
    s, got = service(conn, http)
    s.request("A", "B", "C", 100)
    assert got[0].status == "offline"
    s.request("A", "B", "C", 100)
    assert len(http.calls) == 2


def test_server_busy_is_not_cached(qapp, conn):
    http = FakeHttp({"/search": (503, {"name": "ServerOverloaded"})})
    s, got = service(conn, http)
    s.request("A", "B", "", None)
    assert got[0].status == "unavailable"
    assert s.cache.get("a|b|") is None


def test_disabled_makes_no_request(qapp, conn):
    http = FakeHttp({})
    s, got = service(conn, http, enabled=False)
    s.request("A", "B", "C", 100)
    assert http.calls == []
    assert got[0].status == "disabled"


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
def music(qtbot, conn):
    clock = Clock()
    media = FakeMedia()
    volume = VolumeService()
    http = FakeHttp(
        {"/get": (200, {"syncedLyrics": LRC}), "/search": (200, [{"syncedLyrics": LRC}])}
    )
    lyrics = LyricsService(conn, http=http)
    page = MusicPage(media, volume, lyrics, Theme(), now=clock)
    qtbot.addWidget(page)
    page.resize(620, 178)
    page.show()
    return type("M", (), dict(page=page, media=media, volume=volume, http=http, clock=clock))


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


def test_track_requests_lyrics_once(music):
    track = Track("Canção", "Alguém", "Disco", None)
    music.media._apply("track", track)
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))  # duração chegou
    assert len(music.http.calls) == 1
    assert music.page.lyrics_view.state == "synced"


def test_timer_only_when_visible_and_playing(music):
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))
    play(music, 2.0)
    assert music.page.timer_active
    assert music.page.lyrics_view.index == 0
    assert music.page.play.accessibleName() == "Pausar"
    play(music, 2.0, playing=False)
    assert not music.page.timer_active
    assert music.page.play.accessibleName() == "Tocar"
    play(music, 2.0)
    music.page.hide()
    assert not music.page.timer_active


def test_lyrics_follow_position(music):
    music.media._apply("track", Track("Canção", "Alguém", "Disco", 200.0))
    play(music, 0.0)
    music.clock.now += timedelta(seconds=8.5)
    music.page._tick()
    assert music.page.lyrics_view.index == 2
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


def test_plain_lyrics_shows_note(qtbot, conn):
    media = FakeMedia()
    http = FakeHttp({"/get": (200, {"plainLyrics": "Linha 1\nLinha 2"})})
    page = MusicPage(media, VolumeService(), LyricsService(conn, http=http), Theme())
    qtbot.addWidget(page)
    media._apply("track", Track("X", "Y", "Z", 100.0))
    assert page.lyrics_view.state == "plain"
    assert page.lyrics_view.plain_note.text() == "letra não sincronizada"
    assert page.lyrics_view.plain_text.text() == "Linha 1\nLinha 2"
