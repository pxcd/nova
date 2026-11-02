import android.content.Context;
import android.media.session.MediaController;
import android.media.session.MediaSessionManager;
import android.media.session.PlaybackState;
import android.os.Looper;
import android.os.SystemClock;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.List;
import org.json.JSONObject;

/** One-shot Netflix media-session probe/control, executed as the authorized ADB shell. */
public final class NovaSeek {
    private static final String PACKAGE = "com.netflix.ninja";
    private static final long START_TOLERANCE_MS = 3000;
    private static boolean commandSent;

    public static void main(String[] args) {
        JSONObject result;
        try {
            String operation = args.length == 0 ? "inspect" : args[0];
            int waitSeconds = args.length < 2 ? 0 : Integer.parseInt(args[1]);
            if ((!operation.equals("inspect") && !operation.equals("seek-zero") && !operation.equals("seek-one-second"))
                    || waitSeconds < 0 || waitSeconds > 45 || args.length > 2) {
                throw new IllegalArgumentException("Usage: NovaSeek inspect|seek-zero|seek-one-second [wait-seconds:0..45]");
            }
            if (Looper.getMainLooper() == null) Looper.prepareMainLooper();
            Context context = shellContext();
            initializeMediaServices();
            MediaSessionManager manager = (MediaSessionManager) context.getSystemService(Context.MEDIA_SESSION_SERVICE);
            result = run(manager, !operation.equals("inspect"), waitSeconds, operation.equals("seek-one-second") ? 1000 : 0);
        } catch (Throwable error) {
            while (error instanceof InvocationTargetException && error.getCause() != null) error = error.getCause();
            result = new JSONObject();
            try {
                result.put("status", "unavailable");
                result.put("command_sent", commandSent);
                result.put("seek_verified", false);
                result.put("error_type", error.getClass().getSimpleName());
                result.put("message", error.getMessage() == null ? "Media-session access failed." : error.getMessage());
            } catch (Exception ignored) { }
        }
        System.out.println("NOVA_SEEK_RESULT=" + result.toString());
        System.exit(0);
    }

    private static Context shellContext() throws Exception {
        // app_process has no Application context. Bootstrap framework services, then
        // attribute media control to com.android.shell, the UID already authorized by ADB.
        Class<?> type = Class.forName("android.app.ActivityThread");
        Method systemMain = type.getDeclaredMethod("systemMain");
        systemMain.setAccessible(true);
        Object thread = systemMain.invoke(null);
        Method getContext = type.getDeclaredMethod("getSystemContext");
        getContext.setAccessible(true);
        Context system = (Context) getContext.invoke(thread);
        return system.createPackageContext("com.android.shell", 0);
    }

    private static void initializeMediaServices() throws Exception {
        // Android 12 initializes this per-process singleton during normal app
        // startup. app_process skips that step; register the same framework client.
        for (String name : new String[] {"android.media.MediaFrameworkPlatformInitializer",
                "android.media.MediaFrameworkInitializer"}) {
            Class<?> initializer = Class.forName(name);
            Method getter = initializer.getDeclaredMethod("getMediaServiceManager");
            if (getter.invoke(null) == null) {
                Class<?> manager = Class.forName("android.media.MediaServiceManager");
                Object service = manager.getDeclaredConstructor().newInstance();
                initializer.getDeclaredMethod("setMediaServiceManager", manager).invoke(null, service);
            }
        }
    }

    private static JSONObject run(MediaSessionManager manager, boolean seek, int waitSeconds, long targetMs) throws Exception {
        long deadline = SystemClock.elapsedRealtime() + waitSeconds * 1000L;
        MediaController selected = null;
        while (true) {
            int matches = 0;
            List<MediaController> sessions = manager.getActiveSessions(null);
            for (MediaController controller : sessions) {
                PlaybackState state = controller.getPlaybackState();
                if (!PACKAGE.equals(controller.getPackageName()) || state == null) continue;
                boolean ready = state.getState() == PlaybackState.STATE_PLAYING
                        || (targetMs == 0 && state.getState() == PlaybackState.STATE_PAUSED);
                if (ready && state.getPosition() >= 0
                        && (state.getActions() & PlaybackState.ACTION_SEEK_TO) != 0) {
                    matches++;
                    selected = controller;
                }
            }
            if (matches > 1) return outcome("ambiguous_session", false, false, "Multiple Netflix players; no command sent.");
            if (matches == 1) break;
            if (SystemClock.elapsedRealtime() >= deadline) {
                return outcome("not_ready", false, false, "No ready Netflix session advertising seek support; no command sent.");
            }
            Thread.sleep(250);
        }
        PlaybackState before = selected.getPlaybackState();
        JSONObject result = outcome("ready", false, false, "Netflix exposes a ready seek-capable media session.");
        result.put("package", PACKAGE);
        result.put("state_before", before.getState());
        result.put("position_before_ms", position(before));
        if (!seek) return result;

        MediaController.TransportControls controls = selected.getTransportControls();
        commandSent = true;
        result.put("target_position_ms", targetMs);
        controls.seekTo(targetMs);
        result.put("command_sent", true);
        long verifyDeadline = SystemClock.elapsedRealtime() + 5000;
        while (true) {
            PlaybackState after = selected.getPlaybackState();
            long current = position(after);
            if (current >= 0 && current <= START_TOLERANCE_MS) {
                boolean playRequested = after.getState() == PlaybackState.STATE_PAUSED;
                if (playRequested) controls.play();
                result.put("status", "seek_confirmed");
                result.put("seek_verified", true);
                result.put("position_after_ms", current);
                result.put("state_after", after.getState());
                result.put("play_requested", playRequested);
                result.put("message", "Netflix reports a playback position within three seconds of the beginning.");
                return result;
            }
            if (SystemClock.elapsedRealtime() >= verifyDeadline) {
                result.put("status", "seek_unverified");
                result.put("position_after_ms", current);
                result.put("message", "Absolute seek was sent but Netflix did not report a position near zero. No UI fallback was used.");
                return result;
            }
            Thread.sleep(200);
        }
    }

    private static long position(PlaybackState state) {
        if (state == null || state.getPosition() < 0) return -1;
        long value = state.getPosition();
        if (state.getState() == PlaybackState.STATE_PLAYING && state.getLastPositionUpdateTime() > 0) {
            value += (long) ((SystemClock.elapsedRealtime() - state.getLastPositionUpdateTime()) * state.getPlaybackSpeed());
        }
        return value;
    }

    private static JSONObject outcome(String status, boolean sent, boolean verified, String message) throws Exception {
        JSONObject result = new JSONObject();
        result.put("status", status);
        result.put("command_sent", sent);
        result.put("seek_verified", verified);
        result.put("message", message);
        return result;
    }
}
