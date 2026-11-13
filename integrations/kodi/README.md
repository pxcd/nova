# Kodi / POV bridge

`pov.py` is deployed to `/config/nova_pov.py` in Home Assistant. It uses Kodi's authenticated HTTP JSON-RPC API at `10.0.0.174:8080`, with `kodi_username` and `kodi_password` loaded only inside HA from `/config/secrets.yaml`. It does not inspect or export POV's own account credentials.

Exposed HA scripts:

- `script.search_kodi_pov`: `query`, `media_type` (`movie` or `series`); returns title/year candidates without playback.
- `script.play_kodi_pov`: `query`, `media_type`, optional `year`; series additionally require explicit `season` and `episode`.

The internal `script.pov_execute_request` opens Kodi with the paired Sony integration and invokes `shell_command.nova_pov_request`. JSON request data is base64-encoded before crossing the shell boundary. Only the two public scripts should be exposed to Assist.

Search, season and episode links are taken from POV's directory listings. Playback accepts only `plugin://plugin.video.pov/` links with the expected route. The installed POV version validated here is 6.10.23. Version changes can change these routes, so recheck them after upgrading.

The bridge does not change source/scraper settings, bypass subscription checks, install add-ons, or add The Loop. Both movies and series open the source picker. Movies require a matching title and release year; episodes require the matching series title and episode or single-season pack. The bridge inspects at most 50 entries, validates the full count before claiming an unavailable resolution or highest tier below 4K, and checks the selected row again before moving back to it. Unknown or mismatched filenames leave selection to the user. Existing video playback is stopped and checked before opening another title. `playback_requested` means Kodi accepted a request; `playback_confirmed` requires matching title and release year (or series/season/episode) in Kodi's active video player. Source filenames and playback metadata cannot guarantee the underlying media is labelled correctly. Explicit latest-episode requests are supported; automatic episode resume is not enabled. If first-air date is present, future placeholders are rejected; missing air dates are not evidence of release.

Run regression checks with:

```sh
python3 -m unittest discover -s integrations/kodi -p 'test_*.py' -v
```

Playback RPC calls are mocked in these tests. Live checks resolved White Chicks (2004) and South Park S28E01 (Twisted Christian). The user confirmed South Park playback and the manually selected Mean Girls (2004) source. The automated movie source-year guard selected a 2004 source and Kodi reported a 1h36m stream, replacing the incorrectly selected 1h52m remake.

Cold startup: the bridge polls JSONRPC.Ping for up to 20 seconds before catalog or playback operations, with one-second probe timeouts. The HA wrapper no longer assumes Kodi is ready after a fixed two-second delay. Authentication failures fail immediately. A stopped-process cold-launch test selected Rush Hour (1998) in about 16 seconds; the user confirmed playback.

After a POV launch, the bridge checks the requested title/year or episode for up to ten player checks after its initial three-second settle. On a match, it selects the lowest-index English audio stream and enables the lowest-index English subtitle stream, using Kodi language tags (`en`, `eng`, `English`, or English locale tags). Missing English tracks leave their existing settings unchanged; no subtitles are downloaded. The response reports `english_tracks` independently from playback verification. Slow/manual source selection beyond the check window requires manual language selection. This applies to NOVA/Assist POV launches, not videos started manually inside Kodi.

## Per-request resolution

`play_kodi_pov` accepts optional `resolution`: `highest` (default), `2160p`/`4K`, `1080p`, `720p`, or `SD`. The Assist tool exposes canonical `2160p` for 4K. The value is separate from the title and never changes POV global settings. An explicit quality must match; missing exact quality returns `resolution_unavailable` after a complete scan without selecting another quality. The default ranks offered identity-matching sources 4K > 1080p > 720p > SD, preserving POV order for ties. A 4K or exact-quality match can be selected immediately. If the full list cannot be checked within the bound or source identity/quality is unclear, manual source selection is required. Highest means highest among sources POV offers under its existing filters, not a guarantee that every provider was scraped.

Example: “Play Hocus Pocus in 1080p on Kodi.” With no quality in the request, the bridge chooses the highest offered quality. The HA-runtime `test_script.py` mocks the internal bridge and checks argument preservation without any TV actions.

Kodi 21 can report an active video using the music playlist ID: `GetActivePlayers` identifies video, while `GetProperties` identifies audio and video-only track setters fail. When this mismatch is detected, the bridge uses bounded native audio/subtitle actions, verifies the selected index after each step, and stops if the active video changes or disappears. Normal video IDs still use direct track setters. Hocus Pocus was live-verified switching from Russian index 0 to English index 7. The misrouted JSON player properties falsely reported zero subtitles: native video booleans confirmed subtitles existed. Subtitle detection/visibility therefore uses the native video read path in this mismatch case. The bridge cycles to Kodi 21’s index-zero/off boundary, selects the first English track, enables it, and independently verifies the native language and visibility. When English is absent after a complete bounded cycle, it restores the original track and visibility. The current movie was live-verified with `VideoPlayer.SubtitlesLanguage=eng` and `VideoPlayer.SubtitlesEnabled=true`.

## Latest aired regular episode

For an explicit “latest episode” request, pass `latest_episode: true` with `media_type: series`, omitting season/episode numbers. The bridge scans all regular seasons (up to 60 seasons and 3000 listed episodes), excludes specials and future-dated placeholders, and ranks valid episodes by air date, season and episode. Dates use Asia/Manila. Missing/invalid dates, conflicting entries, incomplete listings, scan failures, or a newest episode dated today without a release time require clarification; no episode is guessed. A plain series title still requires explicit episode numbers. Air date does not guarantee source availability.

The selected episode uses the normal resolution selector and first-English audio/English-subtitle selection and enabling path. Kodi fallback preserves the latest flag; subscription-app title tools do not support latest resolution, so an unsupported request is not silently resumed instead. Example: “Play the latest episode of South Park in 1080p on Kodi.” Unit, HA wrapper and model-routing checks pass; live metadata/playback validation was unavailable because Kodi was unreachable during deployment.

## Catalog-grounded natural language

Expose `script.browse_kodi_series` to the conversation agent. This generic tool returns regular-season summaries or paginated episode titles/air dates for a selected season. The model interprets natural-language requests against those records and calls the existing play tool with actual season/episode numbers; there is no phrase dictionary or per-show handler. Examples checked in dry runs include pilot, first episode of a penultimate season, last episode of a season, and penultimate episode of a season. Only aired regular episodes count; ambiguous or incomplete metadata requires clarification.

For an authorized Kodi playback request, `prepare_playback=true` on the first browse call may open Kodi before reading its catalog. Information-only questions leave it false and call only the shell metadata bridge; no app launch, video start, or source selection occurs. The bridge strips plugin paths from catalog output, marks unknown/today/future air dates, exposes actual aired-season numbers (including numbering gaps), and provides episode pagination rather than silently truncating a season. Existing latest selection reuses the same metadata reader. Resolution and English audio/enabled-subtitle handling are unchanged after playback. Live metadata validation was unavailable at deployment because Kodi was offline; unit, HA-runtime and model workflow checks passed.
