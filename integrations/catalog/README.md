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
