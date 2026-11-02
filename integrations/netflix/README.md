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
resume retains `/title/<id>?source=30`; movie start-over also uses the watch link. All ordinary
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
requests run their helper after this shared launch and Play step.

## Restart option

`from_start=true` first launches the requested title through the same link and
Play sequence as ordinary playback. Movies and explicit episodes use watch links;
series resume uses its normal title link. This avoids relying on a freshly opened
title page while a prior player is still active.

The hidden `script.netflix_restart_from_playback` then queries `dumpsys media_session`
through ADB up to eight times, with a one-second delay between unsuccessful reads
plus ADB round-trip overhead. A per-run marker rejects stale responses; the shell
filter returns only an active Netflix session. Only reported playing state 3
allows navigation. Missing/inactive sessions, paused state, stale responses, and
loss of Netflix foreground return `needs_netflix_playback` without restart keys.
The Sony's existing `awk` utility was checked; no helper APK or seek API is needed.

After readiness, the helper sends dedicated Pause → waits 700 ms → Back twice
(one second apart) → waits 700 ms → Down → OK. A foreground check before the final
selection blocks it if navigation left Netflix. The two Back presses were tested:
the first left Hubie Halloween paused; the second returned to its movie page with
Resume highlighted. The full updated from-start tool then ran, and Paolo confirmed
Hubie Halloween restarted from the beginning on 2026-11-02.

Ordinary playback sends no readiness queries, Pause, Back, or restart selection.
The HA-runtime tests mock all device services and check exact normal/restart
control order, unchanged movie/series/episode selection, stale/nonplaying/wrong-app
blocking, and failed lookups.

This remains a timed UI fallback. The desired profile must be selected, Back must
return to a title page with Resume focused, and the next row must be Continue from
the beginning. Media-session state does not expose the actual title or identify
the info screen. Cold launches/profile gates and UI-layout changes remain
unverified. `restart_requested` means the sequence was sent, while
`restart_verified=false` explicitly means zero-position playback was not measured
by the script. The agent says “Restart requested” rather than asserting confirmed
playback from zero. The helper remains hidden from Assist.
