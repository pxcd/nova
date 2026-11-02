# HBO Resume / Restart

`script.play_hbo_title` adds a default-off boolean `from_start`. It uses the original PH subscription catalog lookup. After validating the title link, it force-stops only `com.wbd.stream`, verifies a per-run ADB marker, returns Home and launches the title link. A cold launch establishes the profile picker: after eight seconds it selects the previously confirmed highlighted profile. Playback requests wait five more seconds, then select Resume or move Right once and select Restart. Details-only requests select the profile without pressing Resume/Restart. Normal content/profile/watch-history data is not cleared.

The cold-launch sequence replaces the old unreliable assumption that the profile was already selected. It assumes the desired profile remains highlighted and the current app layout matches the tested Sony UI. The complete Game of Thrones from_start flow took about 19.5 seconds and the user confirmed the selected episode restarted from the beginning. It does not reset the whole series, skip ads, or independently verify playback position.

The HA-runtime test mocks all services and verifies cold/profile ordering, distinct Resume and Restart paths, details-only, and fail-closed catalog/ADB behavior. The global scripts snapshot also contains the existing open-app and confirmed-selection helpers.
