package com.remotecontrol;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public final class ServerKeyFile {
    private ServerKeyFile() {}

    public static Intent createIntent() {
        return new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TITLE, "RemoteControl-access.key");
    }

    public static Intent openIntent() {
        return new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*");
    }

    public static String read(Activity activity, Uri uri) throws IOException {
        try {
            try (InputStream input = activity.getContentResolver().openInputStream(uri)) {
                if (input == null) throw new IOException("선택한 키 파일을 열 수 없습니다.");
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] buffer = new byte[128];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (bytes.size() + count > 128) throw new IOException("키 파일 크기가 올바르지 않습니다.");
                    bytes.write(buffer, 0, count);
                }
                String key = new String(bytes.toByteArray(), StandardCharsets.UTF_8).trim();
                if (!key.matches("[0-9a-fA-F]{64}")) throw new IOException("키 파일에 올바른 64자리 서버 접속 키가 없습니다.");
                return key;
            }
        } catch (SecurityException error) {
            throw new IOException("선택한 키 파일을 읽을 권한이 없습니다.", error);
        }
    }

    public static void write(Activity activity, Uri uri, String key) throws IOException {
        if (!key.matches("[0-9a-fA-F]{64}")) throw new IOException("서버 접속 키는 64자리 hex 형식이어야 합니다.");
        try {
            try (OutputStream output = activity.getContentResolver().openOutputStream(uri, "wt")) {
                if (output == null) throw new IOException("선택한 위치에 키 파일을 저장할 수 없습니다.");
                output.write(key.getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
        } catch (SecurityException error) {
            throw new IOException("선택한 위치에 키 파일을 쓸 권한이 없습니다.", error);
        }
    }

    public static void delete(Activity activity, Uri uri) throws IOException {
        try {
            if (!DocumentsContract.deleteDocument(activity.getContentResolver(), uri))
                throw new IOException("파일 제공자가 키 파일 삭제를 완료하지 않았습니다.");
        } catch (UnsupportedOperationException error) {
            throw new IOException("선택한 위치에서는 파일 삭제를 지원하지 않습니다.", error);
        } catch (SecurityException error) {
            throw new IOException("선택한 키 파일을 삭제할 권한이 없습니다.", error);
        }
    }
}
