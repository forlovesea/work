package com.remotecontrol;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.math.BigInteger;
import java.security.*;
import java.security.cert.X509Certificate;
import java.security.spec.ECGenParameterSpec;
import java.util.Date;
import javax.net.ssl.SSLContext;
import javax.security.auth.x500.X500Principal;

final class Identity {
    final String fingerprint;
    final SSLContext context;
    Identity(android.content.Context diagnosticContext) throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        String alias = "remotecontrol-target-v4";
        if (!store.containsAlias(alias)) {
            KeyPairGenerator generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
                    .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                    // Conscrypt signs a precomputed TLS digest using NONEwithECDSA.
                    .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
                    .setCertificateSubject(new X500Principal("CN=RemoteControl Target"))
                    .setCertificateSerialNumber(BigInteger.ONE)
                    .setCertificateNotBefore(new Date(System.currentTimeMillis() - 86400000L))
                    .setCertificateNotAfter(new Date(System.currentTimeMillis() + 315360000000L)).build());
            generator.generateKeyPair();
        }
        X509Certificate certificate = (X509Certificate) store.getCertificate(alias);
        PrivateKey privateKey = (PrivateKey) store.getKey(alias, null);
        android.security.keystore.KeyInfo info = KeyFactory.getInstance(privateKey.getAlgorithm(), "AndroidKeyStore")
                .getKeySpec(privateKey, android.security.keystore.KeyInfo.class);
        Diagnostics.record(diagnosticContext, "target", "TLS identity=v4 authorizedDigests="
                + java.util.Arrays.toString(info.getDigests()), null);
        try {
            Tls.verifyEcdsaSigningKey(privateKey, certificate.getPublicKey());
            Diagnostics.record(diagnosticContext, "target", "TLS signing self-check algorithm=NONEwithECDSA verified=true", null);
        } catch (GeneralSecurityException error) {
            Diagnostics.record(diagnosticContext, "target", "TLS signing self-check algorithm=NONEwithECDSA failed", error);
            throw error;
        }
        // Retire incompatible identities only after the replacement passes its signing check.
        // Otherwise the default key manager could select the old EC key instead of v4.
        for (String previous : new String[]{"remotecontrol-target-v1", "remotecontrol-target-v2", "remotecontrol-target-v3"}) {
            if (store.containsAlias(previous)) store.deleteEntry(previous);
        }
        fingerprint = Tls.fingerprint(certificate);
        context = Tls.server(store, null);
        Diagnostics.record(diagnosticContext, "target", "TLS provider=" + context.getProvider().getName()
                + " certificateAlgorithm=" + certificate.getPublicKey().getAlgorithm()
                + " certificateSignature=" + certificate.getSigAlgName()
                + " validFrom=" + certificate.getNotBefore() + " validUntil=" + certificate.getNotAfter(), null);
    }
}
