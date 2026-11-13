# NOVA

**NOVA Operates Voice Automations.** A private, iPhone-friendly push-to-talk web client for Home Assistant Assist. Node 22+; no npm dependencies or build step.

## Run

1. Copy `.env.example` to `.env`; fill in your Home Assistant long-lived access token and a NOVA password. Keep this file private.
2. Run `npm run setup:https`. This creates a project-local CA and HTTPS certificate. It does not change system trust.
3. Run `npm start`. Open `https://synapse.local:8787` or the Mac's LAN IP at port 8787.
4. Unlock with `NOVA_PASSWORD`. Enable microphone access, then hold the microphone button while speaking and release to send. Text input is also available.

The configured HA pipeline must have an STT engine, a conversation agent, and a TTS engine. The current pipeline uses local Whisper, GPT-OSS through LM Studio, and local Piper. NOVA reuses a Home Assistant conversation per authenticated browser tab, with three prior exchanges retained by the agent. Clear, a page reload, or five minutes of inactivity starts fresh. HA conversation IDs remain on the server.

## iPhone HTTPS setup

Safari microphone access needs a trusted secure origin. On your own iPhone, on the same Wi-Fi:

1. Download your project CA from `http://10.0.0.150:8788/nova-ca.crt` (replace the address if Synapse changes IP).
2. Install the downloaded profile under Settings → General → VPN & Device Management.
3. Enable **NOVA Local CA** under Settings → General → About → Certificate Trust Settings.
4. Open `https://10.0.0.150:8787` in Safari, unlock NOVA, and allow microphone access. Share → Add to Home Screen is optional.

Only the public CA certificate is downloadable. The CA private key stays in `.local/ca.key`; never distribute it. Certificates include localhost, synapse.local, and the IPv4 addresses present when generated. Rerun setup after an IP change; the CA is preserved. Alternatively provide trusted certificates as `.local/server.key` and `.local/server.crt`.

For Mac trust, manually import `.local/ca.crt` into Keychain Access and trust that CA. Do not bypass browser certificate warnings.

For localhost-only HTTP development, run `HOST=127.0.0.1 PORT=8789 node server.js --http`; LAN mode always requires HTTPS and a password. No public tunnel or router forwarding is required.

## Architecture

- The browser captures audio only while push-to-talk is held, converts it to 16 kHz mono PCM, and uploads it after release. Recording is limited to 45 seconds; audio is not written to disk.
- The Node server authenticates the browser with an HttpOnly session cookie and runs the configured HA pipeline over its WebSocket API. HA credentials never reach the browser.
- HA performs STT, invokes the existing agent/tools, and generates TTS. NOVA downloads the response audio server-side and serves it through an authenticated, short-lived local URL.
- Responses and transcripts stay in browser memory. Audio expires from server memory after five minutes. Only one home-control request runs at a time.
- **Stop waiting** disconnects the client; commands already issued by HA may still complete. Push-to-talk is not background wake-word listening. Keep Safari/NOVA in the foreground.

No service worker caches authenticated responses or audio. Nothing depends on a third-party font or CDN.

## Automated checks

`npm test` checks PCM conversion, HA audio framing, conversation isolation and expiry, fresh and follow-up requests, late timeout handling, and the audio proxy boundary. Actual microphone permissions, playback, and certificate trust must also be tested on an iPhone.

## Versioned setup

`home-assistant/` contains the NOVA-owned HA scripts, secret-referencing catalog requests, shell bridge configuration and current agent instructions, with restore notes. Provider-specific code/tests are under `integrations/`. Netflix, HBO Max, Kodi POV, Apple TV+ and Prime Video have been tested on the Sony; The Loop and Apple Music are postponed.

Keep `.env`, `.local/`, populated HA `secrets.yaml`, and ADB pairing keys outside version control. Generate local TLS certificates on each installation. This repository is source/configuration, not a replacement for a separately protected Home Assistant backup.

## Inference providers

The original GPT-OSS pipeline remains NOVA's configured webapp pipeline. **Qwen3 4B** is a separately selectable HA Assist pipeline using the same LM Studio server, model `qwen/qwen3-4b-2507`, and the same NOVA instructions/tools. See `home-assistant/qwen3-4b.json` and `experiments/qwen3-4b/` for reference settings and checks. To change the webapp's provider, deliberately update `HA_PIPELINE_ID` in the private `.env` and restart NOVA.

The Apple FM provider/pipeline was removed from live HA and its compatibility bridge stopped. Historical code and results remain in `experiments/apple-fm/`; the bridge is not required by GPT-OSS or Qwen.

## Start a movie or episode over

Netflix play and restart are separate commands: “Play Hubie Halloween on Netflix,”
then “Restart what is playing on Netflix.” `script.restart_current_netflix` seeks
the current active Netflix video to one second and confirms a reported position
within three seconds of the beginning. It requires Netflix foreground and already
playing; it does not choose/identify a title or relaunch the app. No menu keys,
rewind holds or UI fallback are used. Combined Netflix `from_start=true` requests
are disabled before any TV commands. See `integrations/tv_seek/README.md`.

HBO Max and Prime Video retain their default-off `from_start` title-tool option,
for example “Play Game of Thrones on HBO from the beginning.” These use their tested
profile/UI sequences and do not independently verify zero-position playback.
Ordinary play/resume keeps false. Restart means the selected movie/current episode,
not season one episode one. Apple TV+ start-over remains unsupported.

## Force quit a TV app

Say “Force quit Prime Video,” “Force stop Netflix,” or “Kill the Kodi app.” `script.force_quit_tv_app` is limited to Netflix, HBO Max, Prime Video, Apple TV and Kodi, and verifies the app main process stopped. It does not clear app data. This is distinct from restarting a movie/episode from the beginning. Netflix restart is a separate, current-player seek operation; ordinary playback never invokes it.

GPT-OSS adds one brief, title-specific, spoiler-free quip after successful action requests. The prompt favors dry wit and understatement, avoids factual trivia claims, and uses title-based wordplay or skips the joke for unfamiliar titles. No extra lookup or inference call is added.

## Netflix performer discovery

“Play me an Adam Sandler movie on Netflix” and “Play a Jo Koy special on Netflix” now use a read-only discovery tool before playback. It verifies cast credits and PH subscription links, then chooses from verified candidates when asked to pick one. Recommendation/list requests return options without playing them. Searches are bounded and cached; an incomplete search does not mean no matching titles exist. See `integrations/catalog/README.md`.
