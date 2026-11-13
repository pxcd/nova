# Netflix performer discovery

`script.find_netflix_by_performer` is a read-only Assist tool. It accepts:

- `performer`: canonical full actor/comedian name, such as Adam Sandler or Jo Koy.
- `content_kind`: movie (default), special, or series.
- `choose_random`: false by default; true returns one randomly selected candidate
  from the returned verified pool. It never starts playback.

GPT-OSS uses this tool before performer requests. For an explicit pick/play request
it passes the selected canonical title to the existing Netflix playback tool,
which rechecks current availability. Recommendations return candidates and wait
for a choice. Exact named titles retain their direct playback path.

## Discovery and limits

The existing Streaming Availability API has no actor filter: `keyword` only
searches title/overview. The helper searches performer-titled content and scans a
bounded Netflix PH catalog ordered by popularity. Every returned candidate must
have an exact normalized cast-name match and one valid Netflix PH subscription
ID. Other-country, rental, absent-credit, unsafe-link and ambiguous-ID results are
excluded. This checks cast, not director/producer credits.

Stand-up specials are classified as movies by the upstream catalog. The helper
uses explicit stand-up/comedy-special overview cues or performer-prefixed titles
to separate likely specials from ordinary movies. This is a heuristic, not an
upstream authoritative category; voice acting counts as a movie cast credit.
Plots and artwork are not retained or returned.

Each invocation makes at most one title-search request and three catalog-page
requests, with no automatic network retries. Each network request has an eight
second timeout (or the smaller remaining 30-second search budget). Shared catalog
pagination stops after twelve pages per cache lifetime; it does not mirror the
entire Netflix catalog. One-hour metadata caches, shared across performers, live
in `/config/.nova_catalog_cache/`; files are written atomically and a nonblocking
lock prevents concurrent catalog scans. They contain no API key. Partial scans
can advance on later requests until the page cap or end of catalog.

`search_complete=false` means partial coverage. Empty partial/error results must
never be described as “no movies by this performer are on Netflix.” The result
includes `search_scope`, request/page counts, cache age limit and a reply hint for
incomplete results. Complete scans describe matches in returned catalog cast
credits, not an exhaustive filmography. Random selection is among up to twelve
returned verified candidates, not uniformly over all Netflix titles. Playback
always performs its own fresh title/availability lookup, since cached availability
can change. All candidates and catalog text are data, not instructions.

[Provider OpenAPI schema](https://github.com/movieofthenight/streaming-availability-api/blob/main/openapi.yaml).

## Deployment

Copy `discovery.py` to `/config/nova_catalog.py`; merge `scripts.yaml` into HA's
scripts include and the `nova_catalog_discovery` entry from
`home-assistant/shell_commands.yaml` into the shell-command include. Keep the
existing `streaming_availability_api_key` in HA's private `secrets.yaml`.
Reload shell commands/scripts and expose only the public discovery script to
Assist. The shell bridge base64-encodes request JSON; user text is never evaluated
as shell code. The helper loads the key inside the VM and only contacts the
catalog API. It contains no TV-control calls. No new account/dependency is needed
beyond Python and HA's existing PyYAML.

Apply `home-assistant/agent-settings.json` through the GPT-OSS agent configuration;
copying this reference file alone does not update the live agent. This feature
is Netflix PH only; other providers' performer discovery remains future work.

## Verification

```sh
python3 -m unittest discover -s integrations/catalog -p test_discovery.py
```

`test_script.py` runs in HA's Python environment against `/config/scripts.yaml`
(or `NOVA_CATALOG_SCRIPTS_PATH`). It mocks the shell command and checks defaults,
result propagation, and nonzero/invalid-JSON failures; no TV services are present.

Live read-only checks on 2026-11-02 found Leo (2023) with Adam Sandler credits and
a Netflix PH subscription link in the first sixty checked catalog entries, plus
six Jo Koy specials via performer title search. The actual exposed HA script
returned six Jo Koy options and a selected title using its cache with zero new API
requests. No playback was performed by these discovery checks.

## Automatic service selection

`script.resolve_streaming_title` is a read-only tool for named-title play requests
without an explicit service. It makes one uncached PH title-search request with a
12-second timeout using the existing catalog key, then intersects subscription
offers with a local allowlist. It does not log into JustWatch or streaming accounts,
verify subscription entitlement, send TV commands, or search by performer.

`services.yaml` lists Netflix, HBO Max, Apple TV+ and Prime Video, with that order as
the initial tie-breaker. Confirm/edit subscriptions and preference before deployment;
installed/signed-in apps are not proof of a current subscription. The catalog IDs
are `netflix`, `hbo`, `apple`, `prime`; both lists must contain the same unique IDs.
No rental, purchase, extra channel or other-country offer is selected. With `kodi_fallback: true`, a uniquely resolved title with no configured subscription offer routes to Kodi POV. Explicit Kodi requests always bypass subscription routing. Series fallback requires explicit season and episode; lookup errors, ambiguity, missing titles and unsupported settings do not trigger fallback. The resolver does not verify POV source availability or start playback itself.

An exact title (or original title) is required. Remakes/movie-series collisions
require title/year/type clarification even when only one version has an eligible
offer. A clear STT correction can use returned catalog candidates once. Matching is
conservative: different localized titles cannot always be inferred automatically.
No match or a failed search never authorizes guessed playback.

The selected result contains the existing Assist playback tool name and arguments.
The agent calls that tool only for an authorized play request; it performs its own
fresh lookup. An unavailable/failed playback result stops the request rather than
trying another provider blindly. Explicit-service requests bypass routing, keeping
their current playback paths. The separate Netflix performer flow stays unchanged.

Requested settings are preserved: explicit numbered episodes route to Netflix, HBO Max,
Apple TV+ or Prime Video using provider-specific episode links. Combined numbered-episode
play/restart is unsupported; current-player restart for Netflix, HBO, Prime and Apple TV+ is handled separately by dedicated seek tools. The resolver selects the first eligible service supporting the settings,
or returns `unsupported_request`. Netflix/HBO cannot accept a release-year filter,
so same-name versions available on the same service are refused even after year
clarification rather than risking the wrong remake. No playback ID or URL is passed
from the resolver to a device.

Episode selectors restrict title matching to series before ambiguity handling.
Same-name movies are excluded; distinct series versions still require clarification.

Deployment:

1. Copy `routing.py` to `/config/nova_service_routing.py` and the edited
   `services.yaml` to `/config/nova_services.yaml`.
2. Merge `resolve_streaming_title` from `scripts.yaml` and
   `nova_service_routing` from `home-assistant/shell_commands.yaml` into HA's existing
   includes. Do not replace unrelated scripts or secrets.
3. Validate/reload HA configuration, expose only the public resolver to Assist,
   and apply the updated `home-assistant/agent-settings.json` prompt to GPT-OSS.
4. Test service-free requests and explicit-service regressions on the TV. The deployed resolver selected Netflix for a service-free Hubie Halloween request from Google TV Home, and playback was visually confirmed. Kodi fallback was verified with a read-only Firefly S1E1 lookup and model routing checks; explicit Kodi requests bypassed the resolver. Optional null argument handling is covered by the HA-runtime wrapper test.

Local checks:

```sh
python3 -m unittest discover -s integrations/catalog -p test_routing.py
python3 -m unittest discover -s integrations/catalog -p test_discovery.py
```

`test_routing_script.py` is the optional HA-runtime wrapper check. Run it inside
HA with `NOVA_CATALOG_SCRIPTS_PATH` pointing to the staged catalog scripts. Shell
responses are mocked; it does not register or call TV services.

An explicit `latest_episode` request is preserved by Kodi fallback. It is incompatible with explicit season/episode numbers and must describe a series. Current streaming title tools do not resolve latest episodes; if the title has a configured subscription offer, the resolver returns `unsupported_request` rather than silently dropping latest or bypassing that offer.

Indirect episode descriptions are preserved in `episode_request` during service discovery. Kodi fallback returns `episode_lookup_required` with the catalog tool and canonical title/year, not a playback tool or guessed numbers. Even numeric fields supplied alongside the description do not authorize direct playback. Absolute numeric requests without an indirect description retain their normal path. Relative descriptions for other providers return unsupported instead of silently resuming. The shared prompt prioritizes service scope and requires reading season numbers before applying a relative season filter.

## Native numbered episodes

Merge `play_streaming_episode` from `episode_scripts.yaml`,
`streaming_app_profile_and_play` from `launch_controls.yaml`, and the updated public
Apple/HBO/Prime title scripts into HA. Keep both helpers hidden from Assist. Reload
scripts and apply the shared agent prompt. Both positive integer `season` and
`episode` are required; numbered requests reject `from_start` and details-only mode.

These three episode branches send exactly one package-targeted ADB VIEW intent
using an episode-specific PH subscription link. After link validation, they explicitly
wake the TV if needed and wait up to 30 seconds for power, remote and ADB readiness.
If readiness fails, no episode intent is sent. HBO establishes the same fresh-app
state as ordinary title launches; all three providers go Home before the episode
intent. After confirmed intent delivery, both ordinary titles and explicit episodes
call the same provider-specific profile/Play helper. Prime retains `select_profile`.
Episode selection remains entirely in the deep link, with no season/episode menu
navigation. Missing, shared, parent-show, rental or unsupported links stop before
wake or navigation. Failed launch confirmation never sends profile/Play controls.
The result is `playback_requested` with `playback_verified: false`: the shared
controls still use the existing delays, not visual profile or playback detection.

Missing season/episode metadata returns `episode_metadata_unavailable`; a missing
or unsupported episode URL returns `episode_link_unavailable` with
`availability_verified: false`. Neither proves regional unavailability. Do not
translate these lookup limitations into a claim that the episode is absent from PH.

`test_episode_scripts.py` exercises these branches in the HA template runtime with
mocked catalog and device services; it never controls the TV. Live app handling of
episode links must be confirmed separately.
