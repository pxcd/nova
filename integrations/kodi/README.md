# Kodi / POV bridge

`pov.py` is deployed to `/config/nova_pov.py` in Home Assistant. It uses Kodi's authenticated HTTP JSON-RPC API at `10.0.0.174:8080`, with `kodi_username` and `kodi_password` loaded only inside HA from `/config/secrets.yaml`. It does not inspect or export POV's own account credentials.

Exposed HA scripts:

- `script.search_kodi_pov`: `query`, `media_type` (`movie` or `series`); returns title/year candidates without playback.
- `script.play_kodi_pov`: `query`, `media_type`, optional `year`; series additionally require explicit `season` and `episode`.

The internal `script.pov_execute_request` opens Kodi with the paired Sony integration and invokes `shell_command.nova_pov_request`. JSON request data is base64-encoded before crossing the shell boundary. Only the two public scripts should be exposed to Assist.

Search, season and episode links are taken from POV's directory listings. Playback accepts only `plugin://plugin.video.pov/` links with the expected route. The installed POV version validated here is 6.10.23. Version changes can change these routes, so recheck them after upgrading.

The bridge does not change source/scraper settings, bypass subscription checks, install add-ons, or add The Loop. Both movies and series open the source picker. Movies require a matching title and release year; episodes require the matching series title and episode or single-season pack. The bridge inspects at most 50 entries, validates the full count before claiming an unavailable resolution or highest tier below 4K, and checks the selected row again before moving back to it. Unknown or mismatched filenames leave selection to the user. Existing video playback is stopped and checked before opening another title. `playback_requested` means Kodi accepted a request; `playback_confirmed` requires matching title and release year (or series/season/episode) in Kodi's active video player. Source filenames and playback metadata cannot guarantee the underlying media is labelled correctly. Automatic latest-season discovery and automatic episode resume are intentionally not enabled. If first-air date is present, future placeholders are rejected; missing air dates are not evidence of release.

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

Kodi 21 can report an active video using the music playlist ID: `GetActivePlayers` identifies video, while `GetProperties` identifies audio and video-only track setters fail. When this mismatch is detected, the bridge uses bounded native audio/subtitle actions, verifies the selected index after each step, and stops if the active video changes or disappears. Normal video IDs still use direct track setters. Hocus Pocus was live-verified switching from Russian index 0 to English index 7; that tested source exposed zero subtitle tracks.
