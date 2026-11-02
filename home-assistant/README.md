# Home Assistant configuration snapshot

This directory versions NOVA-owned configuration, not a complete HA backup. It contains no tokens, passwords, pairing keys, VM images or installed third-party add-ons. The snapshot uses this homelab’s private addresses and entity IDs; adjust them for another installation.

## Restore

1. Restore/install HA separately and pair Sony Bravia, Android TV Remote, and Android Debug Bridge. The current TV is `10.0.0.174`; HA is `172.16.152.130`. ADB authorization must be approved on the TV. Do not expose the raw ADB entity to Assist.
2. Install Local OpenAI LLM (`skye-harris/hass_local_openai_llm`, currently 1.14.0) and point it at LM Studio’s OpenAI-compatible API (`http://172.16.152.1:1234/v1`). Apply `agent-settings.json` through the integration’s agent configuration; it is a reference snapshot, not a file HA imports automatically. Advanced request/template options were empty and are omitted. The current model is `openai/gpt-oss-20b`; history is three prior exchanges.
3. Configure the Assist pipeline with local speech recognition and Piper (current voice `en_US-hfc_female-medium`). Update NOVA’s `.env` with the actual pipeline ID and a newly created HA access token. The working HA VM has two vCPUs and 4 GB RAM; its earlier 2 GB allocation produced an STT OOM.
4. Merge `scripts.yaml`, `rest_commands.yaml`, and `shell_commands.yaml` into `/config`, preserving unrelated existing configuration. See `configuration.example.yaml` for include syntax. Existing include filenames can differ; avoid duplicate YAML keys.
5. Copy `../integrations/kodi/pov.py` to `/config/nova_pov.py` and `../integrations/catalog/discovery.py` to `/config/nova_catalog.py`. Enable authenticated Kodi HTTP JSON-RPC on port 8080. Install/configure POV separately; it is not bundled here.
6. Supply the entries in `secrets.example.yaml` in HA’s private `/config/secrets.yaml`. Obtain your own Streaming Availability API key from Movie of the Night. Never commit the populated secrets file.
7. Validate HA configuration and reload scripts. Expose the public scripts to Assist, including the streaming-service, Kodi search/play, Netflix performer discovery, current Netflix restart and TV Home scripts. Keep `script.pov_execute_request` and `script.netflix_restart_from_playback` hidden. Pairings and authorization must be restored manually or from your separately protected HA backup.

Provider-specific notes and mocked-service tests live under `../integrations/`. Prime’s profile step assumes the desired profile is highlighted, based on this TV’s tested behavior. Playback UI timings, app URLs and provider catalogs can change. The agent must not treat a sent command as independently verified playback.

This snapshot does not contain automatic installation or deployment tooling. In particular, never replace an existing HA `.storage` directory with repository files.

`pipelines.json` records the current Assist pipelines, including GPT-OSS and Qwen3 4B. `qwen3-4b.json` describes the separate Qwen agent on the same LM Studio server. Apple FM was removed from live HA; its former connection reference is archived under `../experiments/apple-fm/`. HBO and Prime title tools accept `from_start`. Netflix combined `from_start` is disabled; the separate `restart_current_netflix` requires an already-playing session and the TV-side helper described in `../integrations/tv_seek/README.md`. Keep the legacy Netflix UI restart helper hidden. Apple TV+ restart is postponed.

Netflix performer discovery uses the existing catalog API secret through `shell_command.nova_catalog_discovery`. It never controls the TV. Its generated `/config/.nova_catalog_cache/` is disposable metadata, not restore configuration; do not version it. See `../integrations/catalog/README.md` for bounds and tests.

Service-free named-title playback uses automatic subscription routing with a configured Kodi POV fallback.
Its read-only resolver, local subscription/preference configuration and deployment
steps are described in `../integrations/catalog/README.md`. No JustWatch account
connection is needed. Existing explicit-service tools are unchanged.
