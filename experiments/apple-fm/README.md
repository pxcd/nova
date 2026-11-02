# Apple Foundation Models trial

Tested `fm serve` on macOS 27.2, model `system`, using NOVA's saved instructions and representative OpenAI playback/search tool schemas. The separate HA server and Assist pipeline are named **Apple FM — Experimental**. NOVA remains on GPT-OSS.

Nine nonexecuting cases passed: spoken year, explicit year, original-version follow-up, spoken-year follow-up, explicit episode, Netflix, Apple TV+, Prime, and a repeated Prime action. The five Kodi cases selected search first and then produced correct playback arguments after receiving simulated catalog results. They required two model calls, about 4.5–5.3 seconds combined; direct routing cases were about 2 seconds. These are individual request observations, not an apples-to-apples benchmark or TTFT measurements.

`results.json` records the outputs and limitations. No TV actions occurred during these tests. The complete HA Assist tool bundle and real device control still need a live test. Apple FM is not established as a drop-in quality or latency improvement over GPT-OSS.

Start the server with `fm serve --host 172.16.152.1 --port 1976`. This binds the homelab's VM network address; HA reaches `/v1`. The observed health response marked the on-device `system` model available and `pcc` unavailable in that server context. In HA Assist, select the experimental pipeline to test it; NOVA's webapp continues using the pipeline configured in `.env`. The server must remain running. See `../../home-assistant/apple-fm.experimental.json` and `pipelines.json` for reference settings; these are not automatically imported by HA.
