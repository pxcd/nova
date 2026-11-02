# Instant restart of the current Netflix video

Play a movie/episode normally, then say **“Restart what is playing on Netflix.”**
The public `script.restart_current_netflix` accepts `position_seconds=1`, the only
supported target. The explicit fixed parameter avoids a GPT-OSS zero-argument
calling quirk. No title/query argument is supported.

The script checks Netflix foreground and invokes a small Java helper through the
already authorized ADB shell. The helper requires a unique, already-playing
Netflix media session advertising seek support, sends `seekTo(1000)` once, and
checks the same controller's reported position for up to five seconds. Success
requires a position from 0–3000 ms. If seeking leaves the player paused, the helper
requests play on that same controller. It never launches an app or title.

The wrapper checks a per-run marker, package, target, playing state and position
before returning `restart_confirmed`/`restart_verified=true`. Missing helper,
inactive/paused player, ambiguous session, stale response or unconfirmed position
fails without retries, slow rewind, Home, Back, arrows or OK. It cannot identify
the currently playing title. Combined Netflix title-playback `from_start=true`
remains disabled; the old UI restart helper is hidden and disabled.

## Live evidence — 2 November 2026

| Probe | Observed result |
| --- | --- |
| seekTo(0), including during confirmed playback | Ignored: position continued advancing |
| Dedicated Rewind held for three seconds | Rewound several minutes; rejected as too slow |
| seekTo(1000) during existing playback | Jumped from approximately 82:02 to 88 ms; user confirmed immediate restart without leaving player |
| Complete current-player HA tool | Returned restart_verified=true and playback_verified=true at 539 ms |

The supported path targets one second, not exactly zero. Netflix's reported
position ended up near zero in these tests; no explanation of its internal
zero-vs-nonzero behavior is assumed. Other Netflix/device versions may differ.
The wrapper reports failure rather than introducing a UI fallback.

## Build

No APK, persistent service, root, or permission changes. `toolchain.json` records
the official URLs/checksums used: Temurin JDK 17 (macOS ARM64), Android API 31 and
R8 8.3.37. Verify checksums before extracting. Place dependencies in ignored
`.local/tv-helper-build/`:

- JDK home: `jdk/Contents/Home`
- SDK platform library: `android.jar`
- D8 compiler: `r8-8.3.37.jar`

Run `sh integrations/tv_seek/build.sh`. Override paths with `JDK_HOME`,
`ANDROID_JAR` and `R8_JAR` if needed. Output is
`.local/tv-helper-build/nova-seek.jar`. Build tools/binaries stay outside Git.

## Deploy and restore

Transfer the built JAR to HA's allowed `/media/nova_seek.jar`, then use
`androidtv.upload` to stage `/data/local/tmp/nova-seek-next.jar` on the TV. Verify
its SHA-256 matches the local build before setting mode 0444 and atomically moving
it to `/data/local/tmp/nova-seek.jar`. The JAR must be redeployed if that file is
removed; the script will fail closed rather than fall back to navigation.

Merge `scripts.yaml` into HA and expose only `script.restart_current_netflix` to
Assist. Preserve the disabled legacy helper and normal title-playback guard from
`../netflix/scripts.yaml`. Apply the GPT-OSS instructions in
`home-assistant/agent-settings.json` through the integration's configuration.

The fixed ADB invocation is:

```sh
CLASSPATH=/data/local/tmp/nova-seek.jar app_process /system/bin NovaSeek seek-one-second
```

For read-only inspection replace the operation with `inspect`. Inspection may
report a paused seek-capable session; the supported `seek-one-second` operation
requires playing state 3. `seek-zero` remains a diagnostic operation and is not
used by NOVA. An optional wait argument 0–45 seconds exists for manual diagnostics;
NOVA uses the default zero wait. Results are prefixed `NOVA_SEEK_RESULT=`.

Headless Android 12 startup uses reflection to initialize both platform and module
media-service registries. This bootstrap is version-dependent; it was compiled for
API 31 and checked on the Sony XR-55X90L. No screenshot/UI recognition is required.

`test_script.py` runs inside HA's Python environment with ADB mocked. It checks
foreground, fixed target, package, playing-state, position bounds, stale/malformed
results and explicit failure behavior. No navigation or title-launch services are
registered in that test.

## Additional current-player restart tools

`restart_current_hbo`, `restart_current_prime_video`, and `restart_current_apple_tv` use the same one-second absolute seek with a fixed allowlisted package. Start playback first, then request restart separately in HA Assist or NOVA. The app must be foreground and playing; no title lookup, launch, UI navigation, ad skipping, or automatic retry is performed. HBO and Prime can buffer or play an ad before the restarted content. All three were manually tested on the Sony: Severance (Apple TV+), Fallout (Prime), and Game of Thrones (HBO), with visible restart confirmed. These were playing-session tests; the subsequent four-app cold-start test was stopped by the user after Netflix ignored its seek. Cold-start reliability is not established.
