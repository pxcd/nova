# NOVA capability audit — 2 November 2026

Scope: the existing Sony XR-55X90L, Kodi/POV, Home Mini, Home Assistant VM,
GPT-OSS/LM Studio, catalog API account, and NOVA webapp. Discovery was read-only:
no playback, input, volume, permissions, integrations, or production configuration
changed. No dependencies or subscriptions were added.

## How capability discovery works here

There is no universal streaming SDK. Three existing interfaces provide useful
machine-readable discovery:

- Streaming Availability API: [OpenAPI schema](https://github.com/movieofthenight/streaming-availability-api/blob/main/openapi.yaml).
- Kodi: `JSONRPC.Version`, `JSONRPC.Permission`, and `JSONRPC.Introspect`.
- Sony: `getMethodTypes` on each JSON-RPC service. Actual returned methods must
  still be tested; a method name does not prove usable behavior.

HA's service registry describes globally available actions. Entity feature flags
identify which ones an individual player advertises. Neither guarantees an app
honors a command: Netflix advertised seek but ignored it in our earlier live tests.
None of the current Sony HA media-player entities advertises `SEEK`.

Evidence levels below: **read verified** means a live read or API query succeeded;
**advertised** means the method/schema and access permission exist but its control
action was deliberately not executed; **behavior verified** requires a live result.
These discoveries are a backlog, not newly enabled NOVA tools.

## Recommended backlog

| Priority | Proposed capability | Evidence on this setup | Remaining work |
| --- | --- | --- | --- |
| 1 | Kodi: restart, rewind 30 seconds, jump to a timestamp, pause/resume, select subtitles/audio | JSON-RPC 13.5.0; ControlPlayback granted; Seek, SetSubtitle, SetAudioStream and GetProperties advertised | Add narrow tools; test on an active, seekable video. Kodi had no active player during this audit. |
| 2 | Cross-service recommendations and “where can I watch this?” | PH subscription filter query across Netflix/HBO/Prime/Apple returned HTTP 200 and 20 movies, with pagination | Add catalog search tools and recommendation prompt; verify each selected provider/link before launching. |
| 3 | Performer-constrained random selection | Six Jo Koy titles had matching cast credits and Netflix PH subscription options | Build and verify a candidate set, then choose randomly from eligible results. No dedicated actor filter exists. |
| 4 | HBO, Prime and Apple TV+ season/episode selection | Actual episode-level PH subscription links returned for Game of Thrones, Fallout and Severance | Extend each service's URL validation and tools; test exact episodes on TV. Netflix S1E2 was behavior-verified in the preceding task. |
| 5 | Subtitle/audio/quality questions and expiring-content discovery | Language, quality and availability metadata returned; Netflix PH expiring query returned HTTP 200 and 25 shows, with more pages | Expose read-only tools. Catalog metadata is not proof of the user's account entitlement or active playback quality. |
| 6 | Explicit TV volume/mute/HDMI controls and simple routines | Sony volume read succeeded; HDMI 1–4 and Video sources present; HA advertises volume, source and power actions | Use the correct Sony entity, expose unambiguous voice targets, behavior-test setters. Timed routines require implementation. |
| 7 | NOVA speech or radio on Home Mini | Existing Cast speaker entity and Radio Browser integration are loaded | Test audio playback and a speaker-reachable audio URL. HA has no internal/external URL configured; its VM NAT address needs routing consideration. |
| 8 | Shopping-list voice commands | Shopping list integration loaded and todo.shopping_list present | Check Assist exposure and test add/read/complete through the configured agent. No list contents were read or changed. |

## Recommendations and performer requests

GPT-OSS should interpret taste, suggest candidates, and explain why they fit. The
catalog supplies current PH availability and metadata. Verified options can be
filtered by service, subscription type, genre, year and rating; runtime can then be
filtered locally. The actual schema has no runtime or actor query parameter.
Pagination matters: a single returned page is not a complete catalog.
[Search schema](https://github.com/movieofthenight/streaming-availability-api/blob/main/openapi.yaml).

Example recommendation: “Suggest three clever comedies under 100 minutes on my
subscriptions.” The read-only comedy/rating probe returned titles including Klaus
(98 minutes). Taste is the model's judgment; availability and runtime are data.
Recommendations should wait for a choice before playing.

Example action: “Play me a Jo Koy special on Netflix.” The live title query returned
six credited Netflix PH subscription titles, including Live from Seattle, Comin'
in Hot, In His Elements, Live from the Los Angeles Forum, Live from Brooklyn, and
Blue in the Face (catalog year 2026). It also returned three credited titles without
Netflix PH subscription options, which must be excluded. New catalog titles can
be selected even when the model predates them; no invented plot knowledge is needed.

For “Play a Tom Cruise movie on Netflix,” generate/discover candidates and verify
`cast` plus PH Netflix subscription availability for each. The sampled Top Gun
and Top Gun: Maverick records verified his credit but had no Netflix PH subscription
option. This sample is not an exhaustive Tom Cruise filmography or availability
search. A cast match alone must never authorize a wrong-provider launch. A random
choice should come from code after filtering, rather than an unverified model guess.
[Catalog fields and streaming options](https://docs.movieofthenight.com/guide/shows).

## Streaming episode and metadata findings

| Provider | Read-verified example | Episode URL shape | TV episode behavior |
| --- | --- | --- | --- |
| Netflix | Brooklyn Nine-Nine S1E2, The Tagger, ID 80004162 | /watch/<episode-id> | User confirmed correct episode in preceding task |
| HBO Max | Game of Thrones, Winter Is Coming | play.hbomax.com/video/watch/<uuid> | Not tested; existing title validator must be extended |
| Prime Video | Fallout, The End | app.primevideo.com/detail?gti=<episode-id>&action=play | Not tested; existing profile/Play flow still matters |
| Apple TV+ | Severance, Good News About Hell | tv.apple.com/ph/episode/<slug>/<id> with query parameters | Not tested; existing title validator must accept episode links |

All three non-Netflix reads included subtitle/audio languages and quality; HBO also
included an expiry field. These are discovery data, not APIs for changing native
app subtitles. The expiry endpoint is accessible on the existing account. Some
expiry dates can be unknown; notifications would need a separately requested
schedule and exact-date handling.
[Episode metadata](https://docs.movieofthenight.com/resource/shows),
[availability changes](https://docs.movieofthenight.com/resource/changes).

## Kodi has the strongest direct control surface

The live API exposes absolute/time/percentage seeking and relative seconds;
subtitle on/off/index selection; audio-track index selection; playback time and
available-stream queries; playlist operations; and GUI window/control queries.
Use the queried stream labels to resolve “English subtitles,” not guessed indexes.
These controls operate within Kodi, not Netflix or other native apps.
[API 13.5](https://kodi.wiki/view/JSON-RPC_API/v13.5).

GUI.GetProperties succeeded in the background and identified the Favourites
window and The Loop control label. Favourites.GetFavourites returned 27 entries.
This offers structured navigation shortcuts, but says nothing about whether a
sports scraper's eventual stream will work. The Loop automation remains postponed.

VideoLibrary.GetMovies and GetTVShows both reported zero library items. POV's
remote catalog/history is not automatically Kodi's standard library. Standard
“next unwatched” or saved resume-point queries therefore cannot currently provide
complete POV history. No video was active, so stream availability and actual seek
behavior remain untested in this audit.

## Sony, Cast and voice boundaries

Sony discovery returned native power, audio, input and app-control methods. Volume
information was read successfully (43/100, unmuted), and power saving reported low.
Picture-off power saving, speaker/sound settings and other setters remain untested.
Some Pro-display documentation does not apply to this consumer TV.
[Sony API reference](https://pro-bravia.sony.net/ja/remote-display-control/rest-api/reference/).

getApplicationStatusList returned keyboard/cursor/browser flags. It is not a list
of Netflix foreground/background sessions or info-page detection. getPlayingContentInfo
was denied by HTTP on the direct read attempt. getScreenshot was advertised with
a plane string parameter but was not invoked; working screenshots and screenshot
classification remain unverified. Netflix info/profile-page detection is still
unresolved. Android TV's Watch Next query succeeded but returned no rows, so it
cannot currently supply Continue Watching history.

The existing Android TV Remote entity does report the foreground app, while the
ADB media-player entity still reports Settings/idle inconsistently. Use each
interface for the capability it actually provides. Generic media_seek being
registered in HA does not establish Netflix seek support.
[Android TV Remote limitations](https://www.home-assistant.io/integrations/androidtv_remote/).

Cast can deliver media and TTS to a speaker, but the current integration does not
provide a Home Mini microphone feed or wake-word input to NOVA. Speaker playback
was not exercised. Radio Browser is already installed and supplies radio stations;
NOVA needs a tool to find/select them. Shopping List is another existing non-TV
capability, not yet verified through the GPT agent.
[Cast](https://www.home-assistant.io/integrations/cast/),
[Radio Browser](https://www.home-assistant.io/integrations/radio_browser/),
[Shopping List](https://www.home-assistant.io/integrations/shopping_list/).

## Suggested implementation order

1. Kodi playback controls: narrow, discoverable, directly testable operations.
2. Catalog recommendations/provider lookup and performer-filtered selection.
3. Specific episodes on Prime, HBO and Apple TV+, one provider at a time.
4. Home Mini audio output and radio after confirming audio URL reachability.

No audit finding has been silently exposed to the LLM or enabled in production.
