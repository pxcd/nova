"""Bounded POV bridge with identity-checked resolution and language selection."""

import base64
from datetime import date
import json
import re
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ADDON = "plugin.video.pov"


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value)).casefold()
    return re.sub(r"[^a-z0-9]", "", value)


def plugin_params(path, allowed_modes):
    parsed = urlsplit(path)
    params = parse_qs(parsed.query)
    if (parsed.scheme != "plugin" or parsed.netloc != ADDON
            or params.get("mode", [None])[0] not in allowed_modes):
        raise ValueError("POV returned an unexpected item link; nothing was played.")
    return params


def integer(item, key, params):
    value = item.get(key)
    if value is None or value == "":
        value = params.get(key, [-1])[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def summary(item):
    return {"title": item.get("title") or item.get("label", ""),
            "year": item.get("year", 0)}


def listing(rpc, path):
    plugin_params(path, {"build_movie_list", "build_tvshow_list", "build_season_list", "build_episode_list"})
    result = rpc("Files.GetDirectory", {"directory": path, "media": "video",
                  "properties": ["title", "year", "showtitle", "season", "episode", "firstaired"]})
    return result.get("files", [])


def search(rpc, query, media_type):
    mode, action = (("build_movie_list", "tmdb_movies_search") if media_type == "movie"
                    else ("build_tvshow_list", "tmdb_tv_search"))
    path = "plugin://" + ADDON + "/?" + urlencode({"mode": mode, "action": action, "query": query})
    return listing(rpc, path)[:30]


def resolve(rpc, request):
    query = request.get("query", "")
    media_type = request.get("media_type")
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        return {"status": "failed", "message": "Provide a title up to 200 characters.", "command_sent": False}
    if media_type not in {"movie", "series"}:
        return {"status": "needs_clarification", "message": "Choose movie or series.", "command_sent": False}
    files = search(rpc, query.strip(), media_type)
    candidates = [summary(item) for item in files[:10]]
    if request.get("operation") == "search":
        return {"status": "search_results", "addon": "POV", "media_type": media_type,
                "candidates": candidates, "command_sent": False}
    matches = [item for item in files if normalize(summary(item)["title"]) == normalize(query)]
    if request.get("year") is not None:
        try:
            year = int(request["year"])
        except (TypeError, ValueError):
            return {"status": "failed", "message": "Year must be a number.", "command_sent": False}
        matches = [item for item in matches if item.get("year") == year]
    if len(matches) != 1:
        return {"status": "needs_title_correction" if not matches else "needs_clarification",
                "message": "Use a clearly intended canonical candidate title and retry once, or ask for the year if ambiguous.",
                "candidates": candidates, "command_sent": False}
    item = matches[0]
    path = item.get("file", "")
    result = {**summary(item), "addon": "POV", "media_type": media_type}
    if media_type == "movie":
        plugin_params(path, {"play_media"})
        return {**result, "file": path, "status": "resolved", "command_sent": False}
    season, episode = request.get("season"), request.get("episode")
    # bool is an int in Python, but not a meaningful episode number.
    if any(type(n) not in (int, float) or int(n) != n or n < 1 or n > 999 for n in [season, episode]):
        return {**result, "status": "needs_episode", "command_sent": False,
                "message": "Ask for explicit positive season and episode numbers. Automatic latest-season or resume selection is not enabled."}
    season, episode = int(season), int(episode)
    params = plugin_params(path, {"build_season_list", "build_episode_list"})
    if params["mode"][0] == "build_episode_list" and int(params.get("season", [-1])[0]) == season:
        episodes = listing(rpc, path)
    else:
        seasons = listing(rpc, path)
        found = []
        for season_item in seasons:
            season_path = season_item.get("file", "")
            try:
                values = plugin_params(season_path, {"build_episode_list"})
            except ValueError:
                continue
            if integer(season_item, "season", values) == season:
                found.append(season_path)
        if len(found) != 1:
            return {**result, "season": season, "status": "unavailable", "command_sent": False,
                    "message": "That season was not uniquely present in POV. Nothing was played."}
        episodes = listing(rpc, found[0])
    found = []
    for episode_item in episodes:
        episode_path = episode_item.get("file", "")
        try:
            values = plugin_params(episode_path, {"play_media"})
        except ValueError:
            continue
        if integer(episode_item, "season", values) == season and integer(episode_item, "episode", values) == episode:
            found.append(episode_item)
    if len(found) != 1:
        return {**result, "season": season, "episode": episode, "status": "unavailable", "command_sent": False,
                "message": "That episode was not uniquely present in POV. Nothing was played."}
    selected = found[0]
    aired = selected.get("firstaired", "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", aired or "") and aired > date.today().isoformat():
        return {**result, "season": season, "episode": episode, "status": "unaired", "command_sent": False,
                "message": "POV lists this episode as unaired. Playback was not requested."}
    return {**result, "season": season, "episode": episode, "episode_title": selected.get("title", ""),
            "firstaired": aired or None, "file": selected["file"], "status": "resolved", "command_sent": False}


def source_movie_year(name, title):
    def words(value):
        value = unicodedata.normalize("NFKD", value).casefold()
        return re.sub(r"[^a-z0-9]+", " ", value).strip()
    cleaned, expected = words(name), words(title)
    if not expected:
        return None
    match = re.search(r"\b" + re.escape(expected) + r"\b", cleaned)
    if not match:
        return None
    year = re.search(r"\b((?:19|20)\d{2})\b", cleaned[match.end():])
    return int(year[1]) if year else None


def resolution_value(value):
    if value is None:
        return "highest"
    aliases = {"highest": "highest", "4k": "2160p", "2160p": "2160p",
               "1080p": "1080p", "720p": "720p", "sd": "SD"}
    return aliases.get(value.lower()) if isinstance(value, str) else None


def source_resolution(value):
    tokens = re.findall(r"(?<![a-z0-9])(2160p|4k|1080p|720p|576p|480p|sd)(?![a-z0-9])", value.lower())
    if not tokens:
        return None
    return {"4k": "2160p", "576p": "SD", "480p": "SD", "sd": "SD"}.get(tokens[0], tokens[0])


def source_matches(name, result):
    if result["media_type"] == "movie":
        return source_movie_year(name, result["title"]) == result["year"]
    cleaned = re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", name).casefold())
    title = re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", result["title"]).casefold()).strip()
    if not re.search(r"\b" + re.escape(title) + r"\b", cleaned):
        return False
    episode = re.search(r"\b(?:s(\d{1,3})\s*e(\d{1,3})|(\d{1,3})x(\d{1,3}))\b", cleaned)
    if episode:
        season, number = episode.groups()[:2] if episode[1] else episode.groups()[2:]
        return (int(season), int(number)) == (result["season"], result["episode"])
    # POV resolves the requested episode within a matching single-season pack.
    pack = re.search(r"\bs(\d{1,3})\b", cleaned)
    return bool(pack and int(pack[1]) == result["season"])


def select_source(rpc, result, resolution, sleep):
    keys = {"name": "ListItem.Property(tikiskins.name)",
            "title": "Window.Property(tikiskins.title)",
            "quality": "ListItem.Property(tikiskins.quality)",
            "index": "ListItem.Property(tikiskins.count)",
            "total": "Window.Property(tikiskins.total_results)"}

    def current():
        labels = rpc("XBMC.GetInfoLabels", {"labels": list(keys.values())})
        return {key: labels.get(label, "") for key, label in keys.items()}

    for _ in range(60):
        item = current()
        if normalize(item["title"]) == normalize(result["title"]) and item["name"]:
            break
        sleep(0.5)
    else:
        return {"status": "needs_source_selection"}
    try:
        total = int(item["total"])
    except (TypeError, ValueError):
        return {"status": "needs_source_selection"}
    # Never claim highest quality after only inspecting a truncated source list.
    if not 1 <= total <= 1000:
        return {"status": "needs_source_selection"}
    seen, candidates = set(), []
    rank = {"SD": 0, "720p": 1, "1080p": 2, "2160p": 3}
    for offset in range(min(total, 50)):
        if (normalize(item["title"]) != normalize(result["title"])
                or not item["index"] or item["index"] in seen):
            return {"status": "needs_source_selection"}
        seen.add(item["index"])
        quality = source_resolution(item["quality"]) or source_resolution(item["name"])
        if source_matches(item["name"], result):
            if quality is None and resolution == "highest":
                return {"status": "needs_source_selection"}
            if quality and (resolution == "highest" or quality == resolution):
                # An exact request or the highest supported tier needs no further scan.
                if resolution != "highest" or quality == "2160p":
                    if rpc("Input.Select", {}) == "OK":
                        return {"status": "selected", "selected_resolution": quality}
                    return {"status": "needs_source_selection"}
                candidates.append((rank[quality], offset, dict(item), quality))
        if offset < total - 1:
            rpc("Input.Down", {})
            sleep(0.1)
            item = current()
    if total > 50:
        return {"status": "needs_source_selection"}
    if not candidates:
        return {"status": "resolution_unavailable" if resolution != "highest" else "needs_source_selection"}
    # Keep POV's ordering as the tie-breaker within the highest quality.
    chosen = max(candidates, key=lambda candidate: candidate[0])
    _, offset, expected, quality = chosen
    for _ in range((offset - (total - 1)) % total):
        rpc("Input.Down", {})
        sleep(0.1)
    item = current()
    if item != expected:
        return {"status": "needs_source_selection"}
    if rpc("Input.Select", {}) != "OK":
        return {"status": "needs_source_selection"}
    return {"status": "selected", "selected_resolution": quality}



def select_track_action(rpc, playerid, kind, index, count, sleep):
    """Work around Kodi 21 returning a video session with its music playlist ID."""
    current = "currentaudiostream" if kind == "audio" else "currentsubtitle"
    properties = [current] + (["subtitleenabled"] if kind == "subtitles" else [])
    for _ in range(min(count + 2, 34)):
        active = rpc("Player.GetActivePlayers", {})
        videos = [p for p in active if p.get("type") == "video"]
        if len(videos) != 1 or videos[0]["playerid"] != playerid:
            return False
        state = rpc("Player.GetProperties", {"playerid": playerid, "properties": properties})
        enabled = state.get("subtitleenabled") is True
        if (state.get(current) or {}).get("index") == index and (kind == "audio" or enabled):
            return True
        action = "audionextlanguage" if kind == "audio" else ("nextsubtitle" if enabled else "showsubtitles")
        if rpc("Input.ExecuteAction", {"action": action}) != "OK":
            return False
        sleep(0.25)
    return False


def prefer_english(rpc, playerid, sleep=time.sleep):
    """Select the first English tracks on the verified player, without changing defaults."""
    properties = ["type", "audiostreams", "subtitles", "currentaudiostream", "currentsubtitle", "subtitleenabled"]
    try:
        tracks = rpc("Player.GetProperties", {"playerid": playerid, "properties": properties})
    except (OSError, ValueError, RuntimeError):
        return {"audio": "unverified", "subtitles": "unverified"}
    outcome = {}
    for kind, key, current, method, argument in [
            ("audio", "audiostreams", "currentaudiostream", "Player.SetAudioStream", "stream"),
            ("subtitles", "subtitles", "currentsubtitle", "Player.SetSubtitle", "subtitle")]:
        candidates = [track for track in tracks.get(key, [])
                      if type(track.get("index")) is int and track["index"] >= 0
                      and str(track.get("language", "")).lower().replace("_", "-").split("-")[0]
                      in {"en", "eng", "english"}]
        if not candidates:
            outcome[kind] = "not_available"
            continue
        index = min(track["index"] for track in candidates)
        try:
            # GetActivePlayers can report video/0 while GetProperties(0) reports audio.
            # Kodi's video-only SetAudioStream/SetSubtitle reject that playlist ID.
            if tracks.get("type") == "audio":
                confirmed = select_track_action(rpc, playerid, kind, index, len(tracks.get(key, [])), sleep)
                outcome[kind] = "selected" if confirmed else "unverified"
                continue
            if ((tracks.get(current) or {}).get("index") != index
                    or (kind == "subtitles" and not tracks.get("subtitleenabled"))):
                params = {"playerid": playerid, argument: index}
                if kind == "subtitles":
                    params["enable"] = True
                if rpc(method, params) != "OK":
                    outcome[kind] = "unverified"
                    continue
            after = rpc("Player.GetProperties", {"playerid": playerid,
                        "properties": [current] + (["subtitleenabled"] if kind == "subtitles" else [])})
            confirmed = (after.get(current) or {}).get("index") == index
            if kind == "subtitles":
                confirmed = confirmed and after.get("subtitleenabled") is True
            outcome[kind] = "selected" if confirmed else "unverified"
        except (OSError, ValueError, RuntimeError):
            outcome[kind] = "unverified"
    return outcome


def perform(rpc, request, sleep=time.sleep):
    if request.get("operation") not in {"search", "resolve", "play"}:
        return {"status": "failed", "message": "Unsupported operation.", "command_sent": False}
    resolution = resolution_value(request.get("resolution"))
    if resolution is None:
        return {"status": "invalid_resolution", "command_sent": False,
                "message": "Use highest, 2160p/4K, 1080p, 720p or SD. Nothing was played."}
    result = resolve(rpc, request)
    path = result.pop("file", None)
    if result["status"] != "resolved" or request["operation"] != "play":
        return result
    plugin_params(path, {"play_media"})
    # POV can retain the old stream while attaching the new title's metadata.
    active = rpc("Player.GetActivePlayers", {})
    videos = [player for player in active if player.get("type") == "video"]
    if videos:
        for player in videos:
            rpc("Player.Stop", {"playerid": player["playerid"]})
        for _ in range(10):
            if not any(player.get("type") == "video" for player in rpc("Player.GetActivePlayers", {})):
                break
            sleep(0.2)
        else:
            return {**result, "status": "failed", "command_sent": False,
                    "message": "Kodi did not finish stopping the previous video. The new title was not opened."}
    # Inspect quality and identity before selecting a movie or episode source.
    parsed = urlsplit(path)
    params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "autoplay"]
    path = urlunsplit(parsed._replace(query=urlencode(params + [("autoplay", "false")])))
    if rpc("Player.Open", {"item": {"file": path}}) != "OK":
        return {**result, "status": "failed", "message": "Kodi did not accept the playback request."}
    result.update(status="playback_requested", command_sent=True, playback_verified=False,
                  requested_resolution=resolution,
                  english_tracks={"audio": "not_applied", "subtitles": "not_applied"},
                  message="POV accepted the playback request. It may still be finding sources or waiting for source selection; playback is not verified.")
    try:
        selection = select_source(rpc, result, resolution, sleep)
    except (OSError, ValueError, RuntimeError):
        selection = {"status": "needs_source_selection"}
    result["source_selection_verified"] = selection["status"] == "selected"
    if not result["source_selection_verified"]:
        return {**result, "status": selection["status"],
                "message": "No source was selected. The requested resolution and title/year or episode could not be confirmed within the offered source list. Do not substitute a resolution or retry automatically; manual source selection may be needed."}
    result["selected_resolution"] = selection["selected_resolution"]
    sleep(3)
    for attempt in range(10):
        try:
            active = rpc("Player.GetActivePlayers", {})
            video = next((p for p in active if p.get("type") == "video"), None)
            if video:
                playing = rpc("Player.GetItem", {"playerid": video["playerid"],
                              "properties": ["title", "showtitle", "season", "episode", "year"]}).get("item", {})
                title = playing.get("showtitle") if result["media_type"] == "series" else playing.get("title")
                matched = normalize(title or "") == normalize(result["title"])
                if result["media_type"] == "series":
                    matched = matched and playing.get("season") == result["season"] and playing.get("episode") == result["episode"]
                else:
                    matched = matched and bool(result.get("year")) and playing.get("year") == result["year"]
                if matched:
                    result.update(status="playback_confirmed", playback_verified=True,
                                  message="Kodi reports the requested title/episode in its active video player.")
                    result["english_tracks"] = prefer_english(rpc, video["playerid"], sleep)
                    break
        except (OSError, ValueError, RuntimeError):
            # Do not turn a failed post-check into a second playback attempt.
            break
        if attempt < 9:
            sleep(1)
    return result


class KodiUnavailable(RuntimeError):
    pass


def wait_for_kodi(rpc, sleep=time.sleep, monotonic=time.monotonic):
    deadline = monotonic() + 20
    while True:
        try:
            if rpc("JSONRPC.Ping", {}, timeout=1) == "pong":
                return
        except KodiUnavailable:
            pass
        if monotonic() >= deadline:
            raise KodiUnavailable("Kodi did not become ready within 20 seconds. No playback command was sent.")
        sleep(0.5)


class KodiRPC:
    def __init__(self, username, password):
        credential = base64.b64encode((username + ":" + password).encode()).decode()
        self.authorization = "Basic " + credential

    def __call__(self, method, params, timeout=12):
        data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        request = Request("http://10.0.0.174:8080/jsonrpc", data=data,
                          headers={"Content-Type": "application/json", "Authorization": self.authorization})
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            raise RuntimeError("Kodi HTTP error " + str(error.code)) from None
        except (URLError, TimeoutError):
            raise KodiUnavailable("Kodi is not reachable. Open Kodi on the TV, then try again.") from None
        if "error" in result:
            # Do not echo raw plugin error data, which could contain private paths.
            raise RuntimeError("Kodi rejected " + method + ": " + str(result["error"].get("message", "unknown error")))
        return result["result"]


def main():
    try:
        import yaml  # Provided by Home Assistant; only needed for credential loading.
        with open("/config/secrets.yaml") as source:
            secrets = yaml.safe_load(source) or {}
        rpc = KodiRPC(str(secrets["kodi_username"]), str(secrets["kodi_password"]))
        if len(sys.argv) != 2 or len(sys.argv[1]) > 10000:
            raise ValueError("Invalid request.")
        request = json.loads(base64.b64decode(sys.argv[1], validate=True))
        wait_for_kodi(rpc)
        result = perform(rpc, request)
    except Exception as error:
        message = str(error) if isinstance(error, (ValueError, RuntimeError)) else "Kodi request failed. Check connectivity and saved credentials."
        result = {"status": "failed", "command_sent": False, "message": message}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
