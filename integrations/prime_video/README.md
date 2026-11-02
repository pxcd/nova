# Prime Video on the Sony

The scripts use the existing PH streaming catalog lookup and ADB entity `media_player.android_tv_10_0_0_174`. Title links are restricted to supported Prime Video URL formats and launched explicitly in `com.amazon.amazonvideo.livingroom`. Rentals, purchases and add-on channels are excluded. Multiple valid subscription links within one exact catalog title use the first supported catalog URL; distinct title/year matches still require clarification.

`script.play_prime_video_title` accepts canonical `query`, optional `year`, `start_playback` (default true), and `select_profile` (default true for this Sony). Observed title launches show the already-highlighted desired profile: the script opens the title, waits five seconds, selects that profile, then waits five seconds and presses Play once for playback requests. Set `select_profile=false` if the app no longer requires that step. Screen detection is unavailable: Prime exposes no useful accessibility labels and playback-state reports were unreliable on this TV. No ad-skipping commands are sent. ADB delivery is checked, not actual video playback.

`script.launch_prime_video_living_room` opens the app. `script.confirm_prime_video_selection` sends one OK only after the user confirms the desired profile or Play button is highlighted; it is not an automatic recovery tool.

The HA-runtime test in `test_script.py` mocks catalog and device services and removes waits. It checks the configurable profile sequence, details-only, year collisions, link variants, unsupported/rental links, lookup failure, and failed ADB launch. Manual tests confirmed a Prime profile → Fallout Play screen → OK sequence started an ad followed by the show.
