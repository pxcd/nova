# Netflix title and episode playback

`script.play_netflix_title` accepts `query`, optional `season` and `episode`, and
`from_start` (default false). For example: “Play Brooklyn Nine-Nine season 1,
episode 2 on Netflix.” Keep the series title in `query`; supply both numbers as
positive integers. Requests without episode numbers retain normal Netflix resume.

Explicit episodes request `series_granularity=episode` from the existing Streaming
Availability API. The selector matches a unique `Season N` label, selects that
season's episode by its position in the catalog, and validates the episode's PH
Netflix subscription link. It launches the episode `/watch/<id>?source=30` link,
using the Home → link → dedicated Play sequence. No season-menu key navigation is needed.
Missing numbers, unsupported season labels, out-of-range episodes, movies with
episode arguments, and absent episode links return an error without TV commands.
There is no fallback to a series resume link. Catalog projection excludes plots,
artwork, other countries, and unrequested seasons to stay below HA template limits.

2026-11-02 live check: Brooklyn Nine-Nine S1E2 resolved to “The Tagger”, Netflix ID
`80004162`; Paolo confirmed the Sony opened the correct episode. Other series and
catalog numbering conventions remain unverified. Netflix supplies no useful title
metadata through its media session, so the tool reports the command and resolved
episode, not independently verified playback. Profile selection remains an
assumption. GPT-OSS was also checked with nonexecuting tool calls: explicit S1E2
included both numbers; ordinary resume omitted them.

`test_episodes.py` runs inside the HA Python environment with mocked services. It
checks episode links, input validation, missing availability, reordered seasons,
oversized catalog data, normal Play, and preservation of explicit restart.

## Normal playback

Ordinary movie and explicit episode launches use `/watch/<id>?source=30`. Series
resume and movie start-over requests retain `/title/<id>?source=30`. All ordinary
launches send Home → selected link, wait up to 15 seconds
for Netflix foreground, allow two seconds to settle, then send a dedicated
`media_player.media_play` through Android TV Remote. No OK or directional selection
is used. If Netflix is not confirmed in foreground, Play is blocked. Successful
command delivery returns `playback_requested`, `play_command_sent=true`, and
`playback_verified=false`.

The user confirmed dedicated Play started Joe Rogan: Burn the Boats after both
title and watch links had left it on the info/rating screen. A later warm switch using a title-page link plus Play resumed Edge of Tomorrow
instead of the requested Uncut Gems. A direct watch link plus Play switched to
Uncut Gems correctly. After deploying this routing-only fix, a plain White Chicks
request through the complete shared script switched away from Uncut Gems; the
user confirmed playback. Performer selection and exact-title requests use this
same launch path. Foreground detection does not identify the loaded title,
splash screen or profile picker; those timing cases remain best effort. Restart
requests return through their existing branch before this normal-play step.

## Restart option

`script.play_netflix_title` adds a default-off boolean `from_start`. Normal playback sends the same catalog-selected title link as before. For restart, the script waits two seconds, then its hidden helper selects the row below Resume directly on the freshly opened title page, before idle autoplay/resume. It never presses Back.

Netflix can autoplay from its title page. The old eight-second wait plus Back could navigate to the previous title: White Chicks was requested but Brooklyn Nine-Nine's old page was restarted. The corrected complete B99 → White Chicks from_start transition was tested and the user confirmed White Chicks started from the beginning.

This is a timed Sony Netflix UI sequence, not a seek API. It assumes the desired profile is selected, the requested title page is ready after the delay, and the initial Resume button is focused. The foreground-app check prevents acting in a different app but cannot verify the title or timestamp. `restart_requested` is not independently verified zero-position playback. The helper keeps its legacy internal entity ID `script.netflix_restart_from_playback` and stays hidden from Assist.

The HA-runtime test mocks all services and verifies normal dedicated Play and its foreground guard, direct title-page restart with no Back, wrong-app rejection and catalog failure. Restarting an episode never means starting the whole series at S01E01.
