package com.aiblog.monitor

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class Vault(context: Context) {
    private val prefs = context.getSharedPreferences("vault", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("blog-monitor", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("blog-monitor", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    @Synchronized fun put(name: String, value: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val encoded = Base64.encodeToString(cipher.iv + cipher.doFinal(value.toByteArray()), Base64.NO_WRAP)
        check(prefs.edit().putString(name, encoded).commit()) { "보안 저장 실패" }
    }
    @Synchronized fun get(name: String): String? {
        val encoded = prefs.getString(name, null) ?: return null
        val bytes = Base64.decode(encoded, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12))) }
        return cipher.doFinal(bytes.copyOfRange(12, bytes.size)).toString(Charsets.UTF_8)
    }
    fun clear() { prefs.edit().clear().commit() }
}

class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    var mock: Boolean get() = prefs.getBoolean("mock", true); set(value) { prefs.edit().putBoolean("mock", value).commit() }
    var origin: String get() = prefs.getString("origin", "https://")!!; set(value) { prefs.edit().putString("origin", value).commit() }
    var deviceId: String get() = prefs.getString("deviceId", "")!!; set(value) { prefs.edit().putString("deviceId", value).commit() }
    var deviceName: String get() = prefs.getString("deviceName", "Android Monitor")!!; set(value) { prefs.edit().putString("deviceName", value).commit() }
    var wifiOnly: Boolean get() = prefs.getBoolean("wifiOnly", true); set(value) { prefs.edit().putBoolean("wifiOnly", value).commit() }
    var configured: Boolean get() = prefs.getBoolean("configured", false); set(value) { prefs.edit().putBoolean("configured", value).commit() }
    val mockCreated: Long get() = prefs.getLong("mockCreated", 0).takeIf { it > 0 } ?: System.currentTimeMillis().also { prefs.edit().putLong("mockCreated", it).commit() }
    val scope: String get() = if (mock) "mock" else "$origin/$deviceId"
}

class LocalStore(context: Context) : SQLiteOpenHelper(context, "monitor.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE events(scope TEXT, id TEXT, sequence INTEGER, body TEXT, PRIMARY KEY(scope,id))")
        db.execSQL("CREATE TABLE sync(scope TEXT PRIMARY KEY, cursor INTEGER NOT NULL, packages TEXT NOT NULL DEFAULT '[]', last_sync TEXT)")
        db.execSQL("CREATE TABLE notified(scope TEXT, id TEXT, PRIMARY KEY(scope,id))")
    }
    override fun onUpgrade(db: SQLiteDatabase, old: Int, new: Int) = Unit
    @Synchronized fun cursor(scope: String): Long = readableDatabase.rawQuery("SELECT cursor FROM sync WHERE scope=?", arrayOf(scope)).use {
        if (it.moveToFirst()) it.getLong(0) else 0
    }
    @Synchronized fun apply(scope: String, rows: List<BlogEvent>) {
        writableDatabase.beginTransaction()
        try {
            rows.sortedBy { it.sequence }.forEach { e ->
                require(e.sequence > 0)
                writableDatabase.insertWithOnConflict("events", null, ContentValues().apply {
                    put("scope", scope); put("id", e.id); put("sequence", e.sequence); put("body", e.json())
                }, SQLiteDatabase.CONFLICT_IGNORE)
            }
            val next = maxOf(cursor(scope), rows.maxOfOrNull { it.sequence } ?: 0)
            writableDatabase.execSQL("INSERT OR IGNORE INTO sync(scope,cursor) VALUES (?,0)", arrayOf(scope))
            writableDatabase.execSQL("UPDATE sync SET cursor=? WHERE scope=?", arrayOf<Any>(next, scope))
            writableDatabase.setTransactionSuccessful()
        } finally { writableDatabase.endTransaction() }
    }
    @Synchronized fun events(scope: String): List<BlogEvent> = readableDatabase.rawQuery(
        "SELECT body FROM events WHERE scope=? ORDER BY sequence DESC LIMIT 1000", arrayOf(scope)).use { c ->
        buildList { while (c.moveToNext()) add(BlogEvent.parse(JSONObject(c.getString(0)))) }
    }
    @Synchronized fun markNotification(scope: String, id: String): Boolean = writableDatabase.insertWithOnConflict(
        "notified", null, ContentValues().apply { put("scope", scope); put("id", id) }, SQLiteDatabase.CONFLICT_IGNORE) != -1L
    @Synchronized fun savePackages(scope: String, json: String) {
        writableDatabase.execSQL("INSERT OR IGNORE INTO sync(scope,cursor) VALUES (?,0)", arrayOf(scope))
        writableDatabase.execSQL("UPDATE sync SET packages=?,last_sync=? WHERE scope=?", arrayOf(json, java.time.Instant.now().toString(), scope))
    }
    fun packages(scope: String) = readableDatabase.rawQuery("SELECT packages FROM sync WHERE scope=?", arrayOf(scope)).use {
        if (it.moveToFirst()) it.getString(0) else "[]"
    }
    fun lastSync(scope: String) = readableDatabase.rawQuery("SELECT last_sync FROM sync WHERE scope=?", arrayOf(scope)).use {
        if (it.moveToFirst()) it.getString(0).orEmpty() else ""
    }
}
