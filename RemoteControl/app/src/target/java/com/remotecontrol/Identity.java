package com.remotecontrol;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.math.BigInteger;
import java.security.*;
import java.security.cert.X509Certificate;
import java.util.Date;
import javax.net.ssl.SSLContext;
import javax.security.auth.x500.X500Principal;

final class Identity {
    final String fingerprint;
    final SSLContext context;
    Identity() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        String alias = "remotecontrol-target-v1";
        if (!store.containsAlias(alias)) {
            KeyPairGenerator generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_RSA, "AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
                    .setKeySize(2048).setDigests(KeyProperties.DIGEST_SHA256, KeyProperties.DIGEST_SHA512)
                    .setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1)
                    .setCertificateSubject(new X500Principal("CN=RemoteControl Target"))
                    .setCertificateSerialNumber(BigInteger.ONE)
                    .setCertificateNotBefore(new Date(System.currentTimeMillis() - 86400000L))
                    .setCertificateNotAfter(new Date(System.currentTimeMillis() + 315360000000L)).build());
            generator.generateKeyPair();
        }
        X509Certificate certificate = (X509Certificate) store.getCertificate(alias);
        fingerprint = Tls.fingerprint(certificate);
        context = Tls.server((PrivateKey) store.getKey(alias, null), certificate);
    }
}
