package com.remotecontrol;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import android.widget.Toast;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Pattern;

public final class Diagnostics {
    private static final String TAG = "RemoteControlDiag";
    private static final String LOG_FILE = "diagnostics.log";
    private static final String OLD_LOG_FILE = "diagnostics.log.1";
    private static final int MAX_LOG_BYTES = 256 * 1024;
    private static final int MAX_FIELD_CHARS = 500;
    private static final AtomicBoolean CRASH_HANDLER_INSTALLED = new AtomicBoolean();
    private static final Pattern CREDENTIAL = Pattern.compile(
            "(?i)(key|token|secret)([\\s\"'=:\\u0000-\\u001f]+)[A-Za-z0-9_+/=-]{8,}");
    private static final Pattern HEX_SECRET = Pattern.compile("(?i)\\b(?:[0-9a-f]{32}|[0-9a-f]{64})\\b");

    private Diagnostics() {}

    public static synchronized void record(Context context, String role, String event, Throwable error) {
        StringBuilder entry = new StringBuilder();
        entry.append(new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.ROOT).format(new Date()))
                .append(" role=").append(sanitize(role))
                .append(" diag=20261008.2")
                .append(" elapsedMs=").append(android.os.SystemClock.elapsedRealtime())
                .append(" thread=").append(sanitize(Thread.currentThread().getName()))
                .append(" android=").append(android.os.Build.VERSION.SDK_INT)
                .append(" device=").append(sanitize(android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL))
                .append(" os=").append(sanitize(android.os.Build.VERSION.RELEASE))
                .append(" event=").append(sanitize(event));
        if (error != null) {
            Throwable cause = error;
            for (int depth = 0; cause != null && depth < 8; depth++, cause = cause.getCause()) {
                entry.append(depth == 0 ? " error=" : " causedBy=").append(sanitize(cause.getClass().getSimpleName()));
                String message = cause.getMessage();
                if (message != null && !message.trim().isEmpty()) {
                    entry.append(": ").append(sanitize(message));
                }
                StackTraceElement[] stack = cause.getStackTrace();
                for (int frame = 0; frame < Math.min(stack.length, 10); frame++) {
                    entry.append(" at=").append(sanitize(stack[frame].toString()));
                }
            }
        }
        entry.append('\n');
        append(context, entry.toString());
    }

    public static void installCrashHandler(Context context, String role) {
        if (!CRASH_HANDLER_INSTALLED.compareAndSet(false, true)) return;
        Context application = context.getApplicationContext();
        Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, error) -> {
            record(application, role, "uncaught exception on " + thread.getName(), error);
            if (previous != null) previous.uncaughtException(thread, error);
        });
    }

    public static synchronized void share(Activity activity) throws IOException {
        File current = new File(activity.getFilesDir(), LOG_FILE);
        File previous = new File(activity.getFilesDir(), OLD_LOG_FILE);
        if (!current.exists() && !previous.exists()) {
            Toast.makeText(activity, "아직 기록된 진단 로그가 없습니다.", Toast.LENGTH_LONG).show();
            return;
        }
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        appendFile(output, previous);
        appendFile(output, current);
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT, "RemoteControl 진단 로그");
        send.putExtra(Intent.EXTRA_TEXT, new String(output.toByteArray(), StandardCharsets.UTF_8));
        try {
            activity.startActivity(Intent.createChooser(send, "진단 로그 공유"));
        } catch (SecurityException error) {
            throw new IOException("진단 로그 공유 화면을 열 수 없습니다.", error);
        }
    }

    static String sanitize(String value) {
        String line = value.replaceAll("\\s+", " ");
        line = CREDENTIAL.matcher(line).replaceAll("$1$2[REDACTED]");
        line = HEX_SECRET.matcher(line).replaceAll("[REDACTED]");
        line = line.trim();
        return line.length() > MAX_FIELD_CHARS ? line.substring(0, MAX_FIELD_CHARS) : line;
    }

    private static void append(Context context, String entry) {
        File current = new File(context.getFilesDir(), LOG_FILE);
        File previous = new File(context.getFilesDir(), OLD_LOG_FILE);
        try {
            if (current.length() + entry.getBytes(StandardCharsets.UTF_8).length > MAX_LOG_BYTES) {
                if (previous.exists() && !previous.delete()) {
                    throw new IOException("기존 진단 로그를 교체할 수 없습니다.");
                }
                if (current.exists() && !current.renameTo(previous)) {
                    throw new IOException("진단 로그를 순환할 수 없습니다.");
                }
            }
            try (FileOutputStream stream = new FileOutputStream(current, true)) {
                stream.write(entry.getBytes(StandardCharsets.UTF_8));
            }
        } catch (IOException | SecurityException error) {
            Log.e(TAG, "Could not persist diagnostic log", error);
        }
    }

    private static void appendFile(ByteArrayOutputStream output, File file) throws IOException {
        if (!file.isFile()) return;
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
        }
    }
}
