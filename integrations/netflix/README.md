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
resume retains `/title/<id>?source=30`. All ordinary
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
is handled by the separate current-player tool, not this launch sequence.

## Restart is a separate current-player command

Play normally first, then say “Restart what is playing on Netflix.” The separate
`script.restart_current_netflix` uses an absolute seek to one second on an already
playing Netflix session. It never launches a title or uses menu navigation. See
`../tv_seek/README.md` for its source, deployment and verification requirements.

The retained `from_start=true` argument returns `unsupported_restart` before any
catalog lookup or TV command. It cannot combine a named-title launch and restart.
The old `script.netflix_restart_from_playback` helper is disabled and hidden.
Normal play and episode selection keep their existing behavior.

The old Pause/Back/Down/OK fallback passed one Hubie test but failed on the next:
two Back presses landed on Netflix's home/Continue Watching menu, so selection
acted on the wrong screen. It is not exposed as a fallback. A current-only rewind
hold worked but was too slow. Direct seek to zero was ignored; the later one-second
seek was confirmed near the beginning by the media session and the user.

HA regression tests check that combined restart and the legacy helper send no
lookup or device commands; ordinary movies, series resume and explicit episodes
continue to use their existing link/Play sequence. The new current-player tool has
its own mocked transport tests and live checks.
