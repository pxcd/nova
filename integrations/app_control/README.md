# Force quit media apps

`script.force_quit_tv_app` accepts one friendly `app` value: Netflix, HBO Max, Prime Video, Apple TV, or Kodi. The implementation maps those exact allowed labels to constant Android package IDs, invokes `am force-stop`, and checks that the app main process is absent. The ADB response must contain a unique per-run success marker; errors, stale results, or a still-running process are not reported as success. Arbitrary package names, system apps and shell input are rejected before any command is sent. App data/sign-in/watch history are not cleared.

Use for explicit “force quit Prime Video” / “kill the Kodi app” requests, not “restart this episode.” Movie/episode start-over requests still use the corresponding playback tool's `from_start` flag. Both GPT-OSS and Qwen have that distinction in their instructions.

The HA-runtime test mocks all services and covers all five package mappings, unknown/injection input rejection, and pending/stale/error completion. A live Prime Video force-quit was verified while Netflix remained in the foreground, preparing Prime for a separate cold-start playback test without opening TV Settings.
