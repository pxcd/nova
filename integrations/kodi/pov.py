"""Small, bounded POV JSON-RPC bridge. Uses POV native autoplay for NOVA playback requests."""

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


def select_movie_source(rpc, title, year, sleep):
    # Cloud sources can match remakes by title alone. Check the visible release
    # filename before selecting; Kodi's playback metadata can describe the wrong stream.
    name_key = "ListItem.Property(tikiskins.name)"
    title_key = "Window.Property(tikiskins.title)"
    def current():
        labels = rpc("XBMC.GetInfoLabels", {"labels": [name_key, title_key]})
        if normalize(labels.get(title_key, "")) != normalize(title):
            return ""
        return labels.get(name_key, "")
    for _ in range(60):
        name = current()
        if name:
            break
        sleep(0.5)
    else:
        return False
    seen = set()
    for _ in range(50):
        if not name or name in seen:
            return False
        seen.add(name)
        if source_movie_year(name, title) == year:
            return rpc("Input.Select", {}) == "OK"
        rpc("Input.Down", {})
        sleep(0.1)
        name = current()
    return False


def perform(rpc, request, sleep=time.sleep):
    if request.get("operation") not in {"search", "resolve", "play"}:
        return {"status": "failed", "message": "Unsupported operation.", "command_sent": False}
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
    # Series use native autoplay. Movies require a title/year-checked source.
    parsed = urlsplit(path)
    params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "autoplay"]
    path = urlunsplit(parsed._replace(query=urlencode(params + [("autoplay", "false" if result["media_type"] == "movie" else "true")])))
    if rpc("Player.Open", {"item": {"file": path}}) != "OK":
        return {**result, "status": "failed", "message": "Kodi did not accept the playback request."}
    if result.get("year"):
        label = "premiered" if result["media_type"] == "series" else "was released"
        result["trivia_fact"] = f"It {label} in {result['year']}."
        result["trivia_source"] = "POV catalog metadata"
    result.update(status="playback_requested", command_sent=True, playback_verified=False,
                  message="POV accepted the playback request. It may still be finding sources or waiting for source selection; playback is not verified.")
    if result["media_type"] == "movie":
        try:
            selected = select_movie_source(rpc, result["title"], result["year"], sleep)
        except (OSError, ValueError, RuntimeError):
            selected = False
        result["source_selection_verified"] = selected
        if not selected:
            return {**result, "status": "needs_source_selection",
                    "message": "Could not select a source with a matching title and release year. Playback is not verified; manual source selection may be needed. Do not retry automatically."}
    sleep(3)
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
    except (OSError, ValueError, RuntimeError):
        # Do not turn a failed post-check into a second playback attempt.
        pass
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
