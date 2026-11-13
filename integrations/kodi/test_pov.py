from datetime import date
import copy
import unittest
from unittest.mock import patch
from pov import perform, latest_episode, browse_episode_catalog, prefer_english, select_subtitle_native, source_resolution, source_movie_year, wait_for_kodi, KodiUnavailable

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
        self.tracks = {"type": "video", "audiostreams": [], "subtitles": [], "currentaudiostream": {}, "currentsubtitle": {}, "subtitleenabled": False}
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
            name = self.source_names[self.source_index]
            return {"Window.Property(tikiskins.title)": self.movie["title"],
                    "ListItem.Property(tikiskins.name)": name,
                    "ListItem.Property(tikiskins.quality)": source_resolution(name) or "",
                    "ListItem.Property(tikiskins.count)": str(self.source_index + 1),
                    "Window.Property(tikiskins.total_results)": str(len(self.source_names))}
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
        if method == "Player.GetProperties":
            return {key: copy.deepcopy(self.tracks[key]) for key in params["properties"]}
        if method == "Player.SetAudioStream":
            self.tracks["currentaudiostream"] = {"index": params["stream"]}
            return "OK"
        if method == "Player.SetSubtitle":
            self.tracks["currentsubtitle"] = {"index": params["subtitle"]}
            self.tracks["subtitleenabled"] = params["enable"]
            return "OK"
        if method == "Player.GetItem":
            return {"item": self.player_item}
        raise AssertionError((method, params))


class NativeSubtitleRPC:
    def __init__(self, languages, index=0, enabled=False):
        self.languages, self.index, self.enabled = languages, index, enabled
        self.actions = []

    def __call__(self, method, params):
        if method == "Player.GetActivePlayers":
            return [{"playerid": 0, "type": "video"}]
        if method == "XBMC.GetInfoBooleans":
            return {"VideoPlayer.HasSubtitles": bool(self.languages), "VideoPlayer.SubtitlesEnabled": self.enabled}
        if method == "XBMC.GetInfoLabels":
            return {"VideoPlayer.SubtitlesLanguage": self.languages[self.index] if self.languages else ""}
        if method == "Input.ExecuteAction":
            action = params["action"]
            self.actions.append(action)
            if action == "showsubtitles":
                self.enabled = not self.enabled
            elif action == "nextsubtitle":
                self.index = (self.index + 1) % len(self.languages)
                if self.index == 0: self.enabled = False
            return "OK"
        raise AssertionError(method)


class EpisodeCatalogRPC:
    def __init__(self, seasons):
        self.seasons = seasons
        self.calls = []
        self.partial = False

    def __call__(self, method, params):
        self.calls.append(method)
        if method != "Files.GetDirectory": raise AssertionError(method)
        path = params["directory"]
        if path == SERIES:
            files = [{"season": n, "file": SEASON.replace("season=28", "season=" + str(n))} for n in self.seasons]
        else:
            from urllib.parse import parse_qs,urlsplit
            season = int(parse_qs(urlsplit(path).query)["season"][0])
            files = [dict(row, season=row.get("season", season), file=row.get("file", EPISODE.replace("season=28", "season=" + str(season)).replace("episode=1", "episode=" + str(row["episode"])))) for row in self.seasons[season]]
        return {"files": files, "limits": {"total": len(files) + int(self.partial)}}


class POVTest(unittest.TestCase):
    def test_default_resolution_scans_for_highest_matching_movie(self):
        rpc = FakeRPC()
        rpc.source_names = ["WHITE CHICKS 2004 720P", "WHITE CHICKS 2024 4K", "WHITE CHICKS 2004 2160P", "WHITE CHICKS 2004 1080P"]
        r = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
        self.assertEqual(r["selected_resolution"], "2160p")
        self.assertEqual(rpc.source_index, 2)

    def test_explicit_resolution_does_not_substitute(self):
        for sources, expected in [(["WHITE CHICKS 2004 4K", "WHITE CHICKS 2004 1080P"], "selected"),
                                  (["WHITE CHICKS 2004 4K", "WHITE CHICKS 2004 720P"], "resolution_unavailable")]:
            rpc = FakeRPC()
            rpc.source_names = sources
            r = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie", "resolution": "1080p"}, sleep=lambda _: None)
            if expected == "selected":
                self.assertEqual(r["selected_resolution"], "1080p")
            else:
                self.assertEqual(r["status"], expected)
                self.assertFalse(any(m == "Input.Select" for m, _ in rpc.calls))

    def test_episode_resolution_preserves_episode_identity(self):
        rpc = FakeRPC()
        rpc.movie["title"] = "South Park"
        rpc.source_names = ["SOUTH PARK S28E02 4K", "SOUTH PARK S28E01 720P", "SOUTH PARK S28E01 1080P"]
        r = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series", "season": 28, "episode": 1}, sleep=lambda _: None)
        self.assertEqual(r["selected_resolution"], "1080p")
        self.assertEqual(rpc.source_index, 2)

    def test_unknown_or_truncated_quality_list_never_claims_highest(self):
        for names in [["WHITE CHICKS 2004 UNKNOWN"], ["WHITE CHICKS 2004 1080P"] * 51]:
            rpc = FakeRPC()
            rpc.source_names = names
            r = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie"}, sleep=lambda _: None)
            self.assertEqual(r["status"], "needs_source_selection")
            self.assertFalse(any(m == "Input.Select" for m, _ in rpc.calls))

    def test_invalid_resolution_never_queries_or_controls_kodi(self):
        rpc = FakeRPC()
        r = perform(rpc, {"operation": "play", "query": "White Chicks", "media_type": "movie", "resolution": "8k"})
        self.assertEqual(r["status"], "invalid_resolution")
        self.assertEqual(rpc.calls, [])

    def test_empty_misrouted_json_subtitles_use_native_read_path(self):
        rpc = FakeRPC()
        rpc.tracks["type"] = "audio"
        with patch("pov.select_subtitle_native", return_value="selected") as native:
            self.assertEqual(prefer_english(rpc, 1, sleep=lambda _: None)["subtitles"], "selected")
            native.assert_called_once()

    def test_browse_exposes_catalog_not_hardcoded_relative_answers(self):
        rpc = EpisodeCatalogRPC({0: [{"episode": 1, "firstaired": "2026-01-01"}],
                                 1: [{"episode": 1, "title": "Pilot", "firstaired": "2025-01-01"}],
                                 5: [{"episode": 1, "firstaired": "2026-01-01"}, {"episode": 7, "firstaired": "2026-02-01"}],
                                 28: [{"episode": 1, "firstaired": "2026-10-01"}],
                                 29: [{"episode": 1, "firstaired": "2027-01-01"}]})
        r = browse_episode_catalog(rpc, SERIES, {}, today=date(2026,11,3))
        self.assertEqual(r["aired_regular_seasons"], [1,5,28])
        self.assertTrue(r["ordering_verified"])
        self.assertEqual(r["seasons"][1]["first_aired_episode"]["episode"], 1)
        self.assertEqual(r["seasons"][1]["last_aired_episode"]["episode"], 7)
        self.assertNotIn("file", str(r))
        self.assertEqual(set(rpc.calls), {"Files.GetDirectory"})

    def test_browse_selected_season_and_pagination(self):
        rpc = EpisodeCatalogRPC({1: [{"episode": i, "firstaired": "2025-01-01"} for i in range(1,102)]})
        r = browse_episode_catalog(rpc, SERIES, {}, season=1, today=date(2026,11,3))
        self.assertEqual((len(r["episodes"]),r["next_episode_offset"]), (100,100))
        r = browse_episode_catalog(rpc, SERIES, {}, season=1, offset=100, today=date(2026,11,3))
        self.assertEqual(r["episodes"][0]["episode"], 101)
        self.assertIsNone(r["next_episode_offset"])
        self.assertEqual(browse_episode_catalog(rpc, SERIES, {}, season=2)["status"], "unavailable")

    def test_browse_uncertain_dates_do_not_certify_season_order(self):
        for aired in [None,"2026-11-03"]:
            rpc = EpisodeCatalogRPC({1: [{"episode": 1, "firstaired": aired}]})
            r = browse_episode_catalog(rpc, SERIES, {}, today=date(2026,11,3))
            self.assertFalse(r["ordering_verified"])

    def test_browse_operation_never_launches_or_changes_player(self):
        rpc = FakeRPC()
        r = perform(rpc, {"operation": "browse", "query": "South Park", "media_type": "series"})
        self.assertEqual(r["status"], "episode_catalog")
        self.assertEqual({m for m,_ in rpc.calls}, {"Files.GetDirectory"})
        for extra in [{"season": True}, {"episode_offset": -1}, {"episode_offset": 100}, {"season": 0}]:
            rpc.calls.clear()
            r = perform(rpc, {"operation":"browse", "query":"South Park", "media_type":"series", **extra})
            self.assertEqual(r["status"], "failed")
            self.assertEqual(rpc.calls, [])

    def test_latest_excludes_future_and_specials_across_unsorted_seasons(self):
        rpc = EpisodeCatalogRPC({29: [{"episode": 1, "firstaired": "2026-12-01"}], 0: [{"episode": 99, "firstaired": "2026-11-01"}],
                                 28: [{"episode": 2, "firstaired": "2026-10-30"}, {"episode": 1, "firstaired": "2026-10-20"}],
                                 27: [{"episode": 9, "firstaired": "2026-10-01"}]})
        r = latest_episode(rpc, SERIES, {"title": "South Park"}, date(2026,11,3))
        self.assertEqual((r["season"], r["episode"]), (28,2))
        self.assertEqual(r["selection_mode"], "latest_aired")
        self.assertEqual(set(rpc.calls), {"Files.GetDirectory"})
        self.assertFalse(r["command_sent"])

    def test_latest_uses_air_date_then_episode_number(self):
        rpc = EpisodeCatalogRPC({1: [{"episode": 8, "firstaired": "2026-10-31"}, {"episode": 9, "firstaired": "2026-10-31"}],
                                 2: [{"episode": 1, "firstaired": "2026-10-30"}]})
        r = latest_episode(rpc, SERIES, {}, date(2026,11,3))
        self.assertEqual((r["season"], r["episode"]), (1,9))

    def test_latest_missing_invalid_and_same_day_dates_require_clarification(self):
        for aired in [None, "", "2026-02-30", "2026-11-03"]:
            rpc = EpisodeCatalogRPC({1: [{"episode": 1, "firstaired": "2026-10-01"}, {"episode": 2, "firstaired": aired}]})
            r = latest_episode(rpc, SERIES, {}, date(2026,11,3))
            self.assertEqual(r["status"], "needs_clarification", aired)
            self.assertNotIn("file", r)

    def test_latest_no_aired_regular_episode_is_unavailable(self):
        for seasons in [{0: [{"episode": 1, "firstaired": "2026-10-01"}]}, {1: [{"episode": 1, "firstaired": "2027-01-01"}]}]:
            self.assertEqual(latest_episode(EpisodeCatalogRPC(seasons), SERIES, {}, date(2026,11,3))["status"], "unavailable")

    def test_latest_partial_or_failed_scan_never_guesses(self):
        rpc = EpisodeCatalogRPC({1: [{"episode": 1, "firstaired": "2026-10-01"}]})
        rpc.partial = True
        self.assertEqual(latest_episode(rpc, SERIES, {}, date(2026,11,3))["status"], "needs_clarification")
        def broken(method, params): raise RuntimeError("unavailable")
        self.assertEqual(latest_episode(broken, SERIES, {}, date(2026,11,3))["status"], "needs_clarification")
        self.assertEqual(latest_episode(rpc, SEASON, {}, date(2026,11,3))["status"], "needs_clarification")

    def test_latest_conflicting_duplicate_or_unsafe_link_never_resolves(self):
        for rows in [[{"episode": 1, "firstaired": "2026-10-01"}, {"episode": 1, "firstaired": "2026-10-02"}],
                     [{"episode": 1, "firstaired": "2026-10-01", "file": "plugin://other/?mode=play_media"}]]:
            self.assertEqual(latest_episode(EpisodeCatalogRPC({1: rows}), SERIES, {}, date(2026,11,3))["status"], "needs_clarification")

    def test_latest_request_cannot_conflict_with_numbers_or_movie(self):
        for request in [{"media_type": "movie"}, {"media_type": "series", "season": 28}, {"media_type": "series", "latest_episode": "yes"}]:
            rpc = FakeRPC()
            r = perform(rpc, dict(query="South Park", operation="play", latest_episode=True) | request, sleep=lambda _: None)
            self.assertEqual(r["status"], "needs_clarification")
            self.assertEqual(rpc.calls, [])

    def test_latest_resolution_reuses_normal_playback_and_english_preferences(self):
        rpc = FakeRPC()
        rpc.playing = True
        rpc.movie["title"] = "South Park"
        rpc.source_names = ["SOUTH PARK S28E01 1080P"]
        rpc.tracks.update(audiostreams=[{"index": 0, "language": "eng"}], subtitles=[{"index": 1, "language": "eng"}])
        r = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series", "latest_episode": True}, sleep=lambda _: None)
        self.assertTrue(r["playback_verified"])
        self.assertEqual((r["season"],r["episode"]), (28,1))
        self.assertEqual(r["english_tracks"], {"audio": "selected", "subtitles": "selected"})
        self.assertTrue(rpc.tracks["subtitleenabled"])

    def test_native_subtitles_select_first_english_and_enable_it(self):
        for index, enabled in [(0, False), (2, True)]:
            rpc = NativeSubtitleRPC(["rus", "eng", "eng"], index, enabled)
            self.assertEqual(select_subtitle_native(rpc, 0, lambda _: None), "selected")
            self.assertEqual(rpc.index, 1)
            self.assertTrue(rpc.enabled)

    def test_native_subtitles_restore_original_when_english_missing(self):
        for index, enabled in [(0, False), (1, False), (1, True)]:
            rpc = NativeSubtitleRPC(["rus", "fra"], index, enabled)
            self.assertEqual(select_subtitle_native(rpc, 0, lambda _: None), "not_available")
            self.assertEqual((rpc.index, rpc.enabled), (index, enabled))

    def test_native_subtitles_do_nothing_when_truly_missing(self):
        rpc = NativeSubtitleRPC([])
        self.assertEqual(select_subtitle_native(rpc, 0, lambda _: None), "not_available")
        self.assertEqual(rpc.actions, [])

    def test_native_subtitles_missing_action_progress_is_bounded(self):
        class Stuck(NativeSubtitleRPC):
            def __call__(self, method, params):
                if method == "Input.ExecuteAction":
                    self.actions.append(params["action"])
                    return "OK"
                return super().__call__(method, params)
        rpc = Stuck(["rus", "eng"], enabled=True)
        self.assertEqual(select_subtitle_native(rpc, 0, lambda _: None), "unverified")
        self.assertEqual(len(rpc.actions), 34)

    def test_first_english_tracks_and_subtitle_enable(self):
        rpc = FakeRPC()
        rpc.tracks.update(audiostreams=[{"index": 0, "language": "jpn"}, {"index": 3, "language": "eng"}, {"index": 1, "language": "en-US"}],
                          subtitles=[{"index": 0, "language": "fra"}, {"index": 1, "language": "English"}, {"index": 2, "language": "eng"}])
        self.assertEqual(prefer_english(rpc, 1), {"audio": "selected", "subtitles": "selected"})
        self.assertIn(("Player.SetAudioStream", {"playerid": 1, "stream": 1}), rpc.calls)
        self.assertIn(("Player.SetSubtitle", {"playerid": 1, "subtitle": 1, "enable": True}), rpc.calls)

    def test_no_english_leaves_existing_tracks_unchanged(self):
        rpc = FakeRPC()
        rpc.tracks.update(audiostreams=[{"index": 0, "language": "fra"}], subtitles=[{"index": 0, "language": "und"}])
        self.assertEqual(prefer_english(rpc, 1), {"audio": "not_available", "subtitles": "not_available"})
        self.assertFalse(any(m.startswith("Player.Set") for m, _ in rpc.calls))

    def test_already_selected_english_is_not_toggled(self):
        rpc = FakeRPC()
        rpc.tracks.update(audiostreams=[{"index": 0, "language": "eng"}], subtitles=[{"index": 0, "language": "eng"}],
                          currentaudiostream={"index": 0}, currentsubtitle={"index": 0}, subtitleenabled=True)
        self.assertEqual(prefer_english(rpc, 1), {"audio": "selected", "subtitles": "selected"})
        self.assertFalse(any(m.startswith("Player.Set") for m, _ in rpc.calls))

    def test_video_music_playlist_id_uses_verified_native_actions(self):
        class WrongPlaylistRPC(FakeRPC):
            def __call__(self, method, params):
                if method == "Input.ExecuteAction":
                    self.calls.append((method, params))
                    action = params["action"]
                    if action == "audionextlanguage":
                        current = self.tracks["currentaudiostream"]["index"]
                        self.tracks["currentaudiostream"] = {"index": (current + 1) % 3}
                    elif action == "showsubtitles":
                        self.tracks["subtitleenabled"] = not self.tracks["subtitleenabled"]
                    elif action == "nextsubtitle":
                        current = self.tracks["currentsubtitle"]["index"]
                        next_index = (current + 1) % 2
                        self.tracks["currentsubtitle"] = {"index": next_index}
                        if next_index == 0: self.tracks["subtitleenabled"] = False
                    return "OK"
                if method == "XBMC.GetInfoBooleans":
                    return {"VideoPlayer.HasSubtitles": True, "VideoPlayer.SubtitlesEnabled": self.tracks["subtitleenabled"]}
                if method == "XBMC.GetInfoLabels" and params["labels"] == ["VideoPlayer.SubtitlesLanguage"]:
                    index = self.tracks["currentsubtitle"]["index"]
                    return {"VideoPlayer.SubtitlesLanguage": ["rus", "eng"][index]}
                return super().__call__(method, params)
        rpc = WrongPlaylistRPC()
        rpc.playing = True
        rpc.tracks.update(type="audio", audiostreams=[{"index": 0, "language": "rus"}, {"index": 1, "language": "rus"}, {"index": 2, "language": "eng"}],
                          subtitles=[{"index": 0, "language": "rus"}, {"index": 1, "language": "eng"}], currentaudiostream={"index": 0}, currentsubtitle={"index": 0})
        self.assertEqual(prefer_english(rpc, 1, sleep=lambda _: None), {"audio": "selected", "subtitles": "selected"})
        self.assertFalse(any(m in {"Player.SetAudioStream", "Player.SetSubtitle"} for m, _ in rpc.calls))

    def test_native_track_workaround_stops_if_video_has_gone(self):
        rpc = FakeRPC()
        rpc.tracks.update(type="audio", audiostreams=[{"index": 7, "language": "eng"}])
        self.assertEqual(prefer_english(rpc, 1, sleep=lambda _: None)["audio"], "unverified")
        self.assertFalse(any(m == "Input.ExecuteAction" for m, _ in rpc.calls))

    def test_audio_failure_does_not_prevent_subtitle_selection(self):
        class AudioFailure(FakeRPC):
            def __call__(self, method, params):
                if method == "Player.SetAudioStream": raise RuntimeError("unsupported")
                return super().__call__(method, params)
        rpc = AudioFailure()
        rpc.tracks.update(audiostreams=[{"index": 1, "language": "eng"}], subtitles=[{"index": 2, "language": "eng"}])
        self.assertEqual(prefer_english(rpc, 1), {"audio": "unverified", "subtitles": "selected"})

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
        rpc.movie["title"] = "South Park"
        rpc.source_names = ["SOUTH PARK S28E01 1080P"]
        result = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series", "season": 28.0, "episode": 1.0}, sleep=lambda _: None)
        self.assertEqual(result["status"], "playback_confirmed")
        self.assertIn("english_tracks", result)
        self.assertIn(("Player.Open", {"item": {"file": EPISODE + "&autoplay=false"}}), rpc.calls)

    def test_delayed_episode_playback_gets_english_tracks(self):
        class DelayedRPC(FakeRPC):
            opened = False
            checks = 0
            def __call__(self, method, params):
                if method == "Player.Open": self.opened = True
                if method == "Player.GetActivePlayers" and self.opened:
                    self.checks += 1
                    self.playing = self.checks >= 3
                return super().__call__(method, params)
        rpc = DelayedRPC()
        rpc.movie["title"] = "South Park"
        rpc.source_names = ["SOUTH PARK S28E01 1080P"]
        rpc.tracks.update(audiostreams=[{"index": 0, "language": "eng"}], subtitles=[{"index": 1, "language": "eng"}])
        result = perform(rpc, {"operation": "play", "query": "South Park", "media_type": "series", "season": 28, "episode": 1}, sleep=lambda _: None)
        self.assertTrue(result["playback_verified"])
        self.assertEqual(result["english_tracks"], {"audio": "selected", "subtitles": "selected"})

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
