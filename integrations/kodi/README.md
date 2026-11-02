# Kodi / POV bridge

`pov.py` is deployed to `/config/nova_pov.py` in Home Assistant. It uses Kodi's authenticated HTTP JSON-RPC API at `10.0.0.174:8080`, with `kodi_username` and `kodi_password` loaded only inside HA from `/config/secrets.yaml`. It does not inspect or export POV's own account credentials.

Exposed HA scripts:

- `script.search_kodi_pov`: `query`, `media_type` (`movie` or `series`); returns title/year candidates without playback.
- `script.play_kodi_pov`: `query`, `media_type`, optional `year`; series additionally require explicit `season` and `episode`.

The internal `script.pov_execute_request` opens Kodi with the paired Sony integration and invokes `shell_command.nova_pov_request`. JSON request data is base64-encoded before crossing the shell boundary. Only the two public scripts should be exposed to Assist.

Search, season and episode links are taken from POV's directory listings. Playback accepts only `plugin://plugin.video.pov/` links with the expected route. The installed POV version validated here is 6.10.23. Version changes can change these routes, so recheck them after upgrading.

The bridge does not change source/scraper settings, bypass subscription checks, install add-ons, or add The Loop. Series use POV native autoplay. Movies open the source picker and select only a filename matching the resolved title and release year, checking at most 50 entries. Unknown or mismatched filenames leave selection to the user. Existing video playback is stopped and checked before opening another title. `playback_requested` means Kodi accepted a request; `playback_confirmed` requires matching title and release year (or series/season/episode) in Kodi's active video player. Source filenames and playback metadata cannot guarantee the underlying media is labelled correctly. Automatic latest-season discovery and automatic episode resume are intentionally not enabled. If first-air date is present, future placeholders are rejected; missing air dates are not evidence of release.

Run regression checks with:

```sh
python3 -m unittest discover -s integrations/kodi -p 'test_*.py' -v
```

Playback RPC calls are mocked in these tests. Live checks resolved White Chicks (2004) and South Park S28E01 (Twisted Christian). The user confirmed South Park playback and the manually selected Mean Girls (2004) source. The automated movie source-year guard selected a 2004 source and Kodi reported a 1h36m stream, replacing the incorrectly selected 1h52m remake.

Cold startup: the bridge polls JSONRPC.Ping for up to 20 seconds before catalog or playback operations, with one-second probe timeouts. The HA wrapper no longer assumes Kodi is ready after a fixed two-second delay. Authentication failures fail immediately. A stopped-process cold-launch test selected Rush Hour (1998) in about 16 seconds; the user confirmed playback.
