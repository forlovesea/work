package com.batterywatch.monitor;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class SettingsStore {
    private final SharedPreferences prefs;
    private static final String ALIAS = "BatteryWatchApiToken";
    SettingsStore(Context context) { prefs = context.getSharedPreferences("connection", Context.MODE_PRIVATE); }
    String url() { return prefs.getString("url", ""); }
    int interval() { return prefs.getInt("interval", 5); }
    private SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }
    String token() throws Exception {
        String encrypted = prefs.getString("token", "");
        if (encrypted.isEmpty()) return "";
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(prefs.getString("iv", ""), Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP)), java.nio.charset.StandardCharsets.UTF_8);
    }
    void save(String url, String token, int interval) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(token.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        boolean ok = prefs.edit().putString("url", url).putInt("interval", interval)
            .putString("token", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)).commit();
        if (!ok) throw new java.io.IOException("설정을 저장하지 못했습니다.");
    }
    void clear() { prefs.edit().clear().apply(); }
}
