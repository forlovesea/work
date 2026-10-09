package com.remotecontrol;

import java.security.*;
import java.security.cert.*;
import java.util.*;
import java.io.IOException;
import javax.net.ssl.*;

public final class Tls {
    /** Exercise the prehashed ECDSA operation used by Conscrypt for Keystore keys. */
    public static void verifyEcdsaSigningKey(PrivateKey privateKey, PublicKey publicKey) throws GeneralSecurityException {
        byte[] challenge = new byte[32];
        new SecureRandom().nextBytes(challenge);
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(challenge);
        Signature signer = Signature.getInstance("NONEwithECDSA");
        signer.initSign(privateKey); signer.update(digest);
        byte[] signature = signer.sign();
        Signature verifier = Signature.getInstance("SHA256withECDSA");
        verifier.initVerify(publicKey); verifier.update(challenge);
        if (!verifier.verify(signature)) throw new SignatureException("TLS signing self-check verification failed");
    }
    public static String fingerprint(java.security.cert.Certificate cert) throws GeneralSecurityException {
        byte[] hash = MessageDigest.getInstance("SHA-256").digest(cert.getEncoded());
        StringBuilder result = new StringBuilder();
        for (byte b : hash) result.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        return result.toString();
    }
    public static SSLContext client(String pin) throws GeneralSecurityException {
        X509TrustManager trust = new X509TrustManager() {
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            public void checkClientTrusted(X509Certificate[] chain, String auth) throws CertificateException { throw new CertificateException(); }
            public void checkServerTrusted(X509Certificate[] chain, String auth) throws CertificateException {
                try {
                    if (chain.length == 0 || !fingerprint(chain[0]).equalsIgnoreCase(pin)) throw new CertificateException("Target 인증서 불일치");
                    chain[0].checkValidity();
                } catch (GeneralSecurityException e) { throw new CertificateException(e); }
            }
        };
        SSLContext context = SSLContext.getInstance("TLSv1.2");
        context.init(null, new TrustManager[]{trust}, new SecureRandom()); return context;
    }
    public static SSLContext server(KeyStore store, char[] password) throws GeneralSecurityException {
        KeyManagerFactory managers = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        managers.init(store, password);
        SSLContext context = SSLContext.getInstance("TLSv1.2");
        context.init(managers.getKeyManagers(), null, new SecureRandom()); return context;
    }
    public static void configure(SSLSocket socket) throws IOException {
        configure(socket, null);
    }
    public static void configure(SSLSocket socket, String keyAlgorithm) throws IOException {
        configure(socket.getSupportedCipherSuites(), socket::setEnabledCipherSuites, keyAlgorithm);
        socket.setEnabledProtocols(new String[]{"TLSv1.2"});
    }
    public static void configure(SSLServerSocket socket) throws IOException {
        configure(socket.getSupportedCipherSuites(), socket::setEnabledCipherSuites, null);
        socket.setEnabledProtocols(new String[]{"TLSv1.2"});
    }
    public static void configure(SSLServerSocket socket, String keyAlgorithm) throws IOException {
        configure(socket.getSupportedCipherSuites(), socket::setEnabledCipherSuites, keyAlgorithm);
        socket.setEnabledProtocols(new String[]{"TLSv1.2"});
    }
    private static void configure(String[] supported, CipherSuiteSetter setter, String keyAlgorithm) throws IOException {
        Set<String> available = new HashSet<>(Arrays.asList(supported));
        String[] rsa = {
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256"
        };
        String[] ecdsa = {
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256"
        };
        List<String> preferred = new ArrayList<>();
        if (keyAlgorithm == null || "EC".equalsIgnoreCase(keyAlgorithm)) preferred.addAll(Arrays.asList(ecdsa));
        if (keyAlgorithm == null || "RSA".equalsIgnoreCase(keyAlgorithm)) preferred.addAll(Arrays.asList(rsa));
        if (preferred.isEmpty()) throw new IOException("지원하지 않는 TLS 서버 키 알고리즘입니다: " + keyAlgorithm);
        List<String> enabled = new ArrayList<>();
        for (String suite : preferred) {
            if (available.contains(suite)) enabled.add(suite);
        }
        if (enabled.isEmpty()) throw new IOException("지원되는 TLS 1.2 ECDHE-RSA 암호화 방식이 없습니다.");
        setter.set(enabled.toArray(new String[0]));
    }
    private interface CipherSuiteSetter {
        void set(String[] suites);
    }
}
