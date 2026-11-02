> Retired from live HA on 2026-11-02 at the user’s request. The provider/pipeline were removed and the bridge stopped. The text below is historical test evidence; Qwen3 4B is the replacement trial provider. Former settings are in `retired-provider.json`.

# Apple Foundation Models trial

Tested `fm serve` on macOS 27.2, model `system`, using NOVA's saved instructions and representative OpenAI playback/search tool schemas. The separate HA server and Assist pipeline are named **Apple FM — Experimental**. NOVA remains on GPT-OSS.

Nine nonexecuting cases passed: spoken year, explicit year, original-version follow-up, spoken-year follow-up, explicit episode, Netflix, Apple TV+, Prime, and a repeated Prime action. The five Kodi cases selected search first and then produced correct playback arguments after receiving simulated catalog results. They required two model calls, about 4.5–5.3 seconds combined; direct routing cases were about 2 seconds. These are individual request observations, not an apples-to-apples benchmark or TTFT measurements.

`results.json` records the outputs and limitations. No TV actions occurred during these tests. The complete HA Assist tool bundle and real device control still need a live test. Apple FM is not established as a drop-in quality or latency improvement over GPT-OSS.

Start the server with `fm serve --host 172.16.152.1 --port 1976`. This binds the homelab's VM network address; HA reaches `/v1`. The observed health response marked the on-device `system` model available and `pcc` unavailable in that server context. In HA Assist, select the experimental pipeline to test it; NOVA's webapp continues using the pipeline configured in `.env`. The server must remain running. See `../../home-assistant/apple-fm.experimental.json` and `pipelines.json` for reference settings; these are not automatically imported by HA.

## Live HA schema compatibility fix

The first live HA attempt returned HTTP 400 from `fm serve`: it cannot decode the `anyOf` schemas in `homeassistant__GetLiveContext.domain` and `media_player__HassSetVolumeRelative.volume_step`, or the untyped `is_volume_muted` fields in the mute/unmute tools. Direct tests reproduced rejection of all four; the script-only tool bundle succeeded.

`fm-schema.js` narrows those known fields to array, signed integer and boolean types that HA accepts. `scripts/fm-bridge.js` forwards the resulting OpenAI request and streams responses unchanged. The full 32-tool payload then succeeded. A real HA conversation with all tools enabled also succeeded (one observed greeting request took 12.8 seconds end to end; this is not TTFT or a performance benchmark). Actual device-tool playback through Apple FM remains unverified.

The experimental HA endpoint is now the bridge at `http://172.16.152.1:1977/v1`; Apple’s server remains on port 1976. See the root README for startup commands. Neither GPT-OSS nor NOVA’s default pipeline was changed. The fixture under `test/fixtures/ha-tool-schemas.json` captures the actual parameter structures used in the diagnostic; descriptions are omitted there because unit tests concern schema conversion.
