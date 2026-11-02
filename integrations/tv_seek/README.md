# Experimental Netflix seek helper

One-shot Android Java helper executed by the TV's already authorized ADB shell.
No APK, persistent service, root, permission grants, or app data changes. Not
connected to NOVA's production restart tool.

## Build

`toolchain.json` records the official artifact URLs and checksums used for the
prototype: Temurin JDK 17 (macOS ARM64), Android API 31, and R8 8.3.37. Verify
those checksums before extracting. Keep dependencies and generated files in
ignored `.local/tv-helper-build/`:

- JDK home: `jdk/Contents/Home`
- SDK platform library: `android.jar`
- D8 compiler: `r8-8.3.37.jar`

Run `sh integrations/tv_seek/build.sh` from the repository. These paths can be
overridden with `JDK_HOME`, `ANDROID_JAR`, and `R8_JAR`. Build output is
`.local/tv-helper-build/nova-seek.jar`.

## Run

Transfer through Home Assistant's allowed `/media` directory, upload using
`androidtv.upload`, verify the SHA-256 on the TV, then install the helper at
`/data/local/tmp/nova-seek.jar` with mode 0444. Execute using `androidtv.adb_command`:

```sh
CLASSPATH=/data/local/tmp/nova-seek.jar app_process /system/bin NovaSeek inspect
CLASSPATH=/data/local/tmp/nova-seek.jar app_process /system/bin NovaSeek seek-zero
```

Optional second argument waits 0–45 seconds for a ready session. The caller must
allow that duration plus five seconds for verification and transport overhead.
The default wait is zero. Inspect never changes playback. The control operation
only targets one Netflix session advertising seek support and playing or paused.
It sends `seekTo(0)` once, checks the reported position for five seconds, and
requests play if the resulting session is paused. There is no UI fallback.

Results are prefixed `NOVA_SEEK_RESULT=`. Android 12 headless startup requires
initializing both platform and module media service registries; reflection is
version-dependent. Netflix exposes no title metadata here, so session readiness
alone cannot prove the requested title is loaded.

## Observed on Sony XR-55X90L / Android 12

2026-11-02: read-only API inspection succeeded after Netflix resumed. Netflix
advertised ACTION_SEEK_TO. A live seek from approximately 991,504 ms returned
`seek_unverified`: the reported position advanced to 996,520 ms rather than zero.
No arrow keys, OK, or Back commands were sent. Advertising seek support does not
establish that Netflix actually honors an external absolute seek request.

The user also confirmed visually that playback continued without restarting.
