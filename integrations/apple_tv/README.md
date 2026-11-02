# Apple TV+ on the Sony

The HA scripts in `scripts.yaml` use the existing PH streaming catalog lookup and the paired Android Debug Bridge entity `media_player.android_tv_10_0_0_174`. The Sony app is `com.apple.atve.sony.appletv`; a package-targeted Android VIEW intent opens the returned title URL. Generic URL launches opened the TV browser during testing.

- `script.play_apple_tv_title`: canonical `query`, optional `year`, `start_playback` (default true). Only Apple subscription links are accepted. True sends Home, the title intent, waits five seconds, then presses OK once. False opens details without OK.
- `script.launch_apple_tv_living_room`: opens the installed app without choosing content.

Only these scripts are exposed to NOVA. Raw ADB control is not exposed. The agent retains three previous exchanges. ADB intent delivery is checked using its success output and a per-run marker; it is not proof of video playback. Profiles, ads and app timing can still interrupt the Play/Resume step.

The HA-runtime test in `test_script.py` mocks all device/catalog services and removes waits. It covers playback, details-only, year collisions, ambiguous matches, rental/wrong-service/unsafe links, rate limits, and failed ADB launch. Run it inside the HA Python environment against the deployed scripts. The user confirmed the complete live Severance lookup → title intent → OK flow resumed playback.
