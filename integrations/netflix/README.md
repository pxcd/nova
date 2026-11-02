# Netflix restart option

`script.play_netflix_title` adds a default-off boolean `from_start`. Normal playback sends the same catalog-selected title link as before. For restart, the script waits two seconds, then its hidden helper selects the row below Resume directly on the freshly opened title page, before idle autoplay/resume. It never presses Back.

Netflix can autoplay from its title page. The old eight-second wait plus Back could navigate to the previous title: White Chicks was requested but Brooklyn Nine-Nine's old page was restarted. The corrected complete B99 → White Chicks from_start transition was tested and the user confirmed White Chicks started from the beginning.

This is a timed Sony Netflix UI sequence, not a seek API. It assumes the desired profile is selected, the requested title page is ready after the delay, and the initial Resume button is focused. The foreground-app check prevents acting in a different app but cannot verify the title or timestamp. `restart_requested` is not independently verified zero-position playback. The helper keeps its legacy internal entity ID `script.netflix_restart_from_playback` and stays hidden from Assist.

The HA-runtime test mocks all services and verifies unchanged normal playback, direct title-page restart with no Back, wrong-app rejection and catalog failure. Restarting an episode never means starting the whole series at S01E01.
