package com.remotecontrol;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import java.util.UUID;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class ServerSettings {
    private static final String ALIAS = "relay-settings-v1";
    public static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences("server", Context.MODE_PRIVATE);
    }
    public static String deviceId(Context context) {
        SharedPreferences prefs = preferences(context);
        String id = prefs.getString("id", "");
        if (id.isEmpty()) { id = UUID.randomUUID().toString().replace("-", ""); prefs.edit().putString("id", id).apply(); }
        return id;
    }
    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }
    public static void save(Context context, String address, String secret, String name) throws Exception {
        if (!secret.matches("[0-9a-fA-F]{64}")) throw new IllegalArgumentException("서버 접속 키는 64자리 영숫자(hex)입니다.");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key());
        String encrypted = Base64.encodeToString(cipher.doFinal(secret.getBytes(java.nio.charset.StandardCharsets.UTF_8)), Base64.NO_WRAP);
        preferences(context).edit().putString("address", address).putString("name", name)
                .putString("secret", encrypted).putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)).apply();
    }
    public static String secret(Context context) {
        try {
            SharedPreferences prefs = preferences(context);
            if (!prefs.contains("secret")) return "";
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(prefs.getString("iv", ""), Base64.NO_WRAP)));
            return new String(cipher.doFinal(Base64.decode(prefs.getString("secret", ""), Base64.NO_WRAP)), java.nio.charset.StandardCharsets.UTF_8);
        } catch (Exception unavailable) { return ""; }
    }
    public static void clearSecret(Context context) {
        preferences(context).edit().remove("secret").remove("iv").apply();
    }
    public static String[] endpoint(String address) {
        String[] parts = address.trim().split(":", -1);
        if (parts.length != 2 || !parts[0].matches("[a-zA-Z0-9.-]{1,253}") || !parts[1].matches("[0-9]{1,5}")
                || !Protocol.relayPort(Integer.parseInt(parts[1])))
            throw new IllegalArgumentException("서버 주소:포트 형식으로 입력하세요. 포트는 55000~60000입니다.");
        return parts;
    }
}
