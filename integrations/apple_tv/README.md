# Apple TV+ on the Sony

The HA scripts in `scripts.yaml` use the existing PH streaming catalog lookup and the paired Android Debug Bridge entity `media_player.android_tv_10_0_0_174`. The Sony app is `com.apple.atve.sony.appletv`; a package-targeted Android VIEW intent opens the returned title URL. Generic URL launches opened the TV browser during testing.

- `script.play_apple_tv_title`: canonical `query`, optional `year`, `start_playback` (default true). Only Apple subscription links are accepted. True wakes the TV if needed, waits up to 30 seconds for TV/control readiness, sends Home and the title intent, waits ten seconds for startup, presses OK once, then sends dedicated Play after two seconds. False opens details without either button. Explicit `season` + `episode` uses the same playback controls after selecting an exact native episode link.
- `script.launch_apple_tv_living_room`: opens the installed app without choosing content.

Only these scripts are exposed to NOVA. Raw ADB control is not exposed. The agent retains three previous exchanges. ADB intent delivery is checked using its success output and a per-run marker; it is not proof of video playback. Profiles, ads and app timing can still interrupt the Play/Resume step.

The HA-runtime test in `test_script.py` mocks all device/catalog services and removes waits. It covers playback, details-only, year collisions, ambiguous matches, rental/wrong-service/unsafe links, rate limits, and failed ADB launch. Run it inside the HA Python environment against the deployed scripts. The user confirmed the complete live Severance lookup → title intent → OK flow resumed playback.

When the catalog has season/episode metadata but omits the Apple episode link, the shared episode script uses `nova_service_routing.py` to read Apple’s public PH show metadata. It validates the parent show ID, numeric season/episode and episode URL before launching. The lookup is bounded to 300 episodes and does not interpret a missing link as regional unavailability. This public website endpoint is not a documented stable API; schema or network failures stop playback. No per-title IDs are hard-coded.

Cold-start acceptance tests must force-quit Apple TV and put the TV in confirmed standby before invoking the public playback tool. Test both ordinary titles and explicit episodes; an app-only restart on an already-awake TV is not sufficient.
