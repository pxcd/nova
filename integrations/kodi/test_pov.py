import copy
import unittest
from pov import perform, source_movie_year, wait_for_kodi, KodiUnavailable

MOVIE = "plugin://plugin.video.pov/?mode=play_media&mediatype=movie&tmdb_id=12153"
SERIES = "plugin://plugin.video.pov/?mode=build_season_list&tmdb_id=2190"
SEASON = "plugin://plugin.video.pov/?mode=build_episode_list&tmdb_id=2190&season=28"
EPISODE = "plugin://plugin.video.pov/?mode=play_media&mediatype=episode&tmdb_id=2190&season=28&episode=1"


class FakeRPC:
    def __init__(self):
        self.calls = []
        self.movie = {"title": "White Chicks", "year": 2004, "file": MOVIE}
        self.series = {"title": "South Park", "year": 1997, "file": SERIES}
        self.episode = {"title": "Episode title", "season": 28, "episode": 1,
                        "firstaired": "2025-01-01", "file": EPISODE}
        self.playing = False
        self.play_after_open = False
        self.source_names = ["WHITE CHICKS 2004 1080P"]
        self.source_index = 0
        self.player_item = {"showtitle": "South Park", "season": 28, "episode": 1}

    def __call__(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == "Files.GetDirectory":
            path = params["directory"]
            if "tmdb_movies_search" in path:
                return {"files": [self.movie]}
            if "tmdb_tv_search" in path:
                return {"files": [self.series]}
            if path == SERIES:
                return {"files": [{"season": 28, "file": SEASON}]}
            if path == SEASON:
                return {"files": [self.episode]}
        if method == "XBMC.GetInfoLabels":
            return {"Window.Property(tikiskins.title)": self.movie["title"],
                    "ListItem.Property(tikiskins.name)": self.source_names[self.source_index]}
        if method == "Input.Down":
            self.source_index = (self.source_index + 1) % len(self.source_names)
            return "OK"
        if method == "Input.Select":
            return "OK"
        if method == "Player.Stop":
            self.play_after_open = self.playing
            self.playing = False
            return "OK"
        if method == "Player.Open":
            self.playing = self.playing or self.play_after_open
            return "OK"
        if method == "Player.GetActivePlayers":
            return [{"type": "video", "playerid": 1}] if self.playing else []
        if method == "Player.GetItem":
            return {"item": self.player_item}
        raise AssertionError((method, params))


class POVTest(unittest.TestCase):
    def test_readiness_retries_only_ping_until_kodi_starts(self):
        calls = []
        def rpc(method, params, timeout):
            calls.append((method, timeout))
            if len(calls) < 3:
                raise KodiUnavailable("starting")
            return "pong"
        wait_for_kodi(rpc, sleep=lambda _: None)
        self.assertEqual(calls, [("JSONRPC.Ping", 1)] * 3)

    def test_readiness_timeout_is_bounded(self):
        clock = [0]
        def sleep(seconds): clock[0] += seconds
        def rpc(method, params, timeout): raise KodiUnavailable("starting")
        with self.assertRaisesRegex(KodiUnavailable, "20 seconds"):
            wait_for_kodi(rpc, sleep=sleep, monotonic=lambda: clock[0])
        self.assertEqual(clock[0], 20)

    def test_readiness_does_not_retry_authentication_failures(self):
        def rpc(method, params, timeout): raise RuntimeError("Kodi HTTP error 401")
        with self.assertRaisesRegex(RuntimeError, "401"):
            wait_for_kodi(rpc, sleep=lambda _: self.fail("Authentication failure must not retry"))

    def test_search_never_plays(self):
        rpc = FakeRPC()
        result = perform(rpc, {"operation": "search", "query": "White Chicks", "media_type": "movie"})
        self.assertEqual(result["candidates"], [{"title": "White Chicks", "year": 2004}])
        self.assertFalse(any(m == "Player.Open" for m, _ in rpc.calls))

    def test_speech_correction_candidates_do_not_play(self):
        rpc = FakeRPC()
        result = perform(rpc, {"operation": "play", "query": "South Pork", "media_type": "series", "season": 28, "episode": 1})
        self.assertEqual(result["status"], "needs_title_correction")
        self.assertFalse(any(m == "Player.Open" for m, _ in rpc.calls))

    def test_series_requires_episode_numbers(self):
        rpc = FakeRPC()
        result = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series"})
        self.assertEqual(result["status"], "needs_episode")
        self.assertFalse(any(m == "Player.Open" for m, _ in rpc.calls))

    def test_exact_episode_uses_returned_link_and_checks_player(self):
        rpc = FakeRPC()
        rpc.playing = True
        result = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series", "season": 28.0, "episode": 1.0}, sleep=lambda _: None)
        self.assertEqual(result["status"], "playback_confirmed")
        self.assertIn(("Player.Open", {"item": {"file": EPISODE + "&autoplay=true"}}), rpc.calls)

    def test_movie_unverified_playback_is_not_reported_as_playing(self):
        rpc = FakeRPC()
        result = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        self.assertEqual(result["status"], "playback_requested")
        self.assertFalse(result["playback_verified"])

    def test_stops_existing_video_before_opening_new_title(self):
        rpc = FakeRPC()
        rpc.playing = True
        perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        methods = [method for method, _ in rpc.calls]
        self.assertLess(methods.index("Player.Stop"), methods.index("Player.Open"))
        self.assertEqual(methods[methods.index("Player.Stop") + 1], "Player.GetActivePlayers")

    def test_failed_stop_never_opens_new_title(self):
        class StuckRPC(FakeRPC):
            def __call__(self, method, params):
                if method == "Player.Stop":
                    self.calls.append((method, params))
                    return "OK"
                return super().__call__(method, params)
        rpc = StuckRPC()
        rpc.playing = True
        result = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(any(m == "Player.Open" for m, _ in rpc.calls))

    def test_same_movie_title_with_wrong_year_is_not_verified(self):
        rpc = FakeRPC()
        rpc.play_after_open = True
        rpc.player_item = {"title": "White Chicks", "year": 2024}
        result = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        self.assertFalse(result["playback_verified"])
        rpc.player_item["year"] = 2004
        result = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        self.assertTrue(result["playback_verified"])

    def test_movie_skips_same_title_source_from_wrong_year(self):
        rpc = FakeRPC()
        rpc.movie.update(title="Mean Girls", year=2004)
        rpc.source_names = ["MEAN GIRLS 2024 2160P", "MEAN GIRLS 2004 2160P"]
        result = perform(rpc, {"operation": "play", "query": "Mean Girls", "media_type": "movie", "year": 2004}, sleep=lambda _: None)
        self.assertTrue(result["source_selection_verified"])
        self.assertEqual(rpc.source_index, 1)
        methods = [method for method, _ in rpc.calls]
        self.assertLess(methods.index("Input.Down"), methods.index("Input.Select"))
        self.assertIn("autoplay=false", next(p["item"]["file"] for m, p in rpc.calls if m == "Player.Open"))

    def test_no_matching_source_never_selects(self):
        rpc = FakeRPC()
        rpc.source_names = ["WHITE CHICKS 2024 1080P", "WHITE CHICKS UNKNOWN"]
        result = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        self.assertEqual(result["status"], "needs_source_selection")
        self.assertFalse(any(m == "Input.Select" for m, _ in rpc.calls))

    def test_release_year_is_after_title_not_a_year_in_the_title(self):
        self.assertEqual(source_movie_year("2001 A Space Odyssey 1968 1080p", "2001: A Space Odyssey"), 1968)
        self.assertIsNone(source_movie_year("Mean Girls 1080p", "Mean Girls"))
        self.assertIsNone(source_movie_year("Other Film 2004", "Mean Girls"))

    def test_future_placeholder_does_not_play(self):
        rpc = FakeRPC()
        rpc.episode["firstaired"] = "2099-01-01"
        result = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series", "season": 28, "episode": 1})
        self.assertEqual(result["status"], "unaired")
        self.assertFalse(any(m == "Player.Open" for m, _ in rpc.calls))

    def test_unexpected_plugin_cannot_be_executed(self):
        rpc = FakeRPC()
        rpc.movie["file"] = "plugin://different.addon/?mode=play_media"
        with self.assertRaises(ValueError):
            perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"})
        self.assertFalse(any(m == "Player.Open" for m, _ in rpc.calls))


if __name__ == "__main__":
    unittest.main()
