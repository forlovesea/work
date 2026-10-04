package com.remotecontrol;

import java.security.*;
import java.security.cert.*;
import java.net.Socket;
import javax.net.ssl.*;

public final class Tls {
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
    public static SSLContext server(PrivateKey key, X509Certificate cert) throws GeneralSecurityException {
        X509ExtendedKeyManager manager = new X509ExtendedKeyManager() {
            public String[] getClientAliases(String type, Principal[] issuers) { return null; }
            public String chooseClientAlias(String[] types, Principal[] issuers, Socket socket) { return null; }
            public String[] getServerAliases(String type, Principal[] issuers) { return "RSA".equals(type) ? new String[]{"target"} : null; }
            public String chooseServerAlias(String type, Principal[] issuers, Socket socket) { return "RSA".equals(type) ? "target" : null; }
            public X509Certificate[] getCertificateChain(String alias) { return new X509Certificate[]{cert}; }
            public PrivateKey getPrivateKey(String alias) { return key; }
        };
        SSLContext context = SSLContext.getInstance("TLSv1.2");
        context.init(new KeyManager[]{manager}, null, new SecureRandom()); return context;
    }
}
