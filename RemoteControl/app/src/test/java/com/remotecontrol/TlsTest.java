package com.remotecontrol;

import org.junit.*;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.security.*;
import java.security.cert.X509Certificate;
import java.util.concurrent.*;
import javax.net.ssl.*;
import static org.junit.Assert.*;

public class TlsTest {
    private static SSLContext target;
    private static SSLContext ecdsaTarget;
    private static String pin;
    private static String ecdsaPin;
    private static Path directory, store, ecdsaStore;
    @BeforeClass public static void identity() throws Exception {
        directory = Files.createTempDirectory("remotecontrol-tls-test");
        store = directory.resolve("test.p12");
        String keytool = Paths.get(System.getProperty("java.home"), "bin", System.getProperty("os.name").startsWith("Windows") ? "keytool.exe" : "keytool").toString();
        Process process = new ProcessBuilder(keytool, "-genkeypair", "-alias", "test", "-keyalg", "RSA", "-keysize", "2048",
                "-sigalg", "SHA256withRSA", "-dname", "CN=localhost", "-ext", "SAN=dns:localhost", "-validity", "1",
                "-storetype", "PKCS12", "-keystore", store.toString(), "-storepass", "test-only-password", "-noprompt")
                .redirectErrorStream(true).redirectOutput(directory.resolve("keytool.log").toFile()).start();
        assertTrue("keytool timeout", process.waitFor(20, TimeUnit.SECONDS)); assertEquals(0, process.exitValue());
        KeyStore keys = KeyStore.getInstance("PKCS12");
        try (InputStream input = Files.newInputStream(store)) { keys.load(input, "test-only-password".toCharArray()); }
        X509Certificate cert = (X509Certificate) keys.getCertificate("test");
        pin = Tls.fingerprint(cert);
        target = Tls.server(keys, "test-only-password".toCharArray());
        ecdsaStore = directory.resolve("ecdsa.p12");
        Process ecdsaProcess = new ProcessBuilder(keytool, "-genkeypair", "-alias", "ecdsa-test", "-keyalg", "EC",
                "-groupname", "secp256r1", "-sigalg", "SHA256withECDSA", "-dname", "CN=localhost",
                "-ext", "SAN=dns:localhost", "-validity", "1", "-storetype", "PKCS12", "-keystore",
                ecdsaStore.toString(), "-storepass", "test-only-password", "-noprompt")
                .redirectErrorStream(true).redirectOutput(directory.resolve("ecdsa-keytool.log").toFile()).start();
        assertTrue("ECDSA keytool timeout", ecdsaProcess.waitFor(20, TimeUnit.SECONDS));
        assertEquals(0, ecdsaProcess.exitValue());
        KeyStore ecdsaKeys = KeyStore.getInstance("PKCS12");
        try (InputStream input = Files.newInputStream(ecdsaStore)) {
            ecdsaKeys.load(input, "test-only-password".toCharArray());
        }
        ecdsaPin = Tls.fingerprint(ecdsaKeys.getCertificate("ecdsa-test"));
        ecdsaTarget = Tls.server(ecdsaKeys, "test-only-password".toCharArray());
    }
    @AfterClass public static void cleanup() throws Exception {
        if (store != null) Files.deleteIfExists(store);
        if (ecdsaStore != null) Files.deleteIfExists(ecdsaStore);
        if (directory != null) {
            Files.deleteIfExists(directory.resolve("keytool.log"));
            Files.deleteIfExists(directory.resolve("ecdsa-keytool.log"));
            Files.deleteIfExists(directory);
        }
    }
    private void handshake(String expectedPin) throws Exception {
        handshake(target, expectedPin, "RSA");
    }
    private void handshake(SSLContext serverContext, String expectedPin, String keyAlgorithm) throws Exception {
        ExecutorService worker = Executors.newSingleThreadExecutor();
        try (SSLServerSocket server = (SSLServerSocket) serverContext.getServerSocketFactory().createServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            Tls.configure(server, keyAlgorithm);
            server.setSoTimeout(5000);
            Future<?> result = worker.submit(() -> {
                try (SSLSocket peer = (SSLSocket) server.accept()) {
                    peer.setSoTimeout(5000); Tls.configure(peer, keyAlgorithm); peer.startHandshake(); peer.getOutputStream().write(42);
                } catch (IOException ignored) { /* Invalid-pin test deliberately aborts the handshake. */ }
            });
            try (SSLSocket client = (SSLSocket) Tls.client(expectedPin).getSocketFactory().createSocket(InetAddress.getLoopbackAddress(), server.getLocalPort())) {
                client.setSoTimeout(5000); Tls.configure(client); client.startHandshake(); assertEquals(42, client.getInputStream().read());
            } finally { result.get(6, TimeUnit.SECONDS); }
        } finally { worker.shutdownNow(); }
    }
    @Test public void pinnedCertificateCanExchangeData() throws Exception { handshake(pin); }
    @Test public void wrongPinRejectsTls() throws Exception {
        try { handshake("00".repeat(32)); fail("wrong pin accepted"); }
        catch (SSLException expected) {}
    }
    @Test public void onlyEphemeralRsaCipherSuitesAreEnabled() throws Exception {
        try (SSLServerSocket server = (SSLServerSocket) target.getServerSocketFactory().createServerSocket()) {
            Tls.configure(server, "RSA");
            assertTrue(server.getEnabledCipherSuites().length > 0);
            for (String suite : server.getEnabledCipherSuites()) {
                assertTrue(suite.startsWith("TLS_ECDHE_RSA_WITH_"));
            }
        }
    }
    @Test public void pinnedEcdsaCertificateCanExchangeData() throws Exception {
        handshake(ecdsaTarget, ecdsaPin, "EC");
    }
    @Test public void ecdsaServerOnlyOffersEcdsaCipherSuites() throws Exception {
        try (SSLServerSocket server = (SSLServerSocket) ecdsaTarget.getServerSocketFactory().createServerSocket()) {
            Tls.configure(server, "EC");
            assertTrue(server.getEnabledCipherSuites().length > 0);
            for (String suite : server.getEnabledCipherSuites()) {
                assertTrue(suite.startsWith("TLS_ECDHE_ECDSA_WITH_"));
            }
        }
    }
    @Test public void prehashedEcdsaSigningMatchesTlsDigest() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC");
        generator.initialize(new java.security.spec.ECGenParameterSpec("secp256r1"));
        KeyPair pair = generator.generateKeyPair();
        Tls.verifyEcdsaSigningKey(pair.getPrivate(), pair.getPublic());
        try {
            Tls.verifyEcdsaSigningKey(pair.getPrivate(), generator.generateKeyPair().getPublic());
            fail("mismatched public key accepted");
        } catch (SignatureException expected) {}
    }
    @Test public void acceptedEcdsaSocketKeepsOnlyEcdsaSuites() throws Exception {
        try (SSLServerSocket server = (SSLServerSocket) ecdsaTarget.getServerSocketFactory()
                .createServerSocket(0, 1, InetAddress.getLoopbackAddress());
             Socket client = new Socket(InetAddress.getLoopbackAddress(), server.getLocalPort());
             SSLSocket accepted = (SSLSocket) server.accept()) {
            Tls.configure(accepted, "EC");
            assertFalse(accepted.getUseClientMode());
            assertTrue(accepted.getEnabledCipherSuites().length > 0);
            for (String suite : accepted.getEnabledCipherSuites()) assertTrue(suite.startsWith("TLS_ECDHE_ECDSA_WITH_"));
        }
    }
}
