# Netflix restart option

`script.play_netflix_title` adds a default-off boolean `from_start`. It opens the catalog-selected title normally, waits eight seconds for playback, then calls the hidden `script.netflix_restart_from_playback` helper. That helper requires Netflix in the foreground, sends Back to the title menu, waits one second, verifies Netflix remains foreground, then selects the row below Resume. The user confirmed this is Continue from the beginning and that White Chicks restarted correctly.

This is a Sony Netflix UI sequence, not a seek API. It assumes the desired profile is already selected and title playback has begun. Screen labels and playback time are not available through the integration; `restart_requested` is not independently verified zero-position playback. The helper stays hidden from Assist. The user must identify a title/service if recent conversation does not supply them; restarting an episode never means starting the series at S01E01.

The HA-runtime test mocks all services and checks unchanged normal playback, explicit restart, app/exit guards and failed catalog lookup. GPT-OSS also produced `from_start=true` for “Play White Chicks on Netflix from the start” in a nonexecuting tool test.
