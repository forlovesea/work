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
    private static String pin;
    private static Path directory, store;
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
        target = Tls.server((PrivateKey) keys.getKey("test", "test-only-password".toCharArray()), cert);
    }
    @AfterClass public static void cleanup() throws Exception {
        if (store != null) Files.deleteIfExists(store);
        if (directory != null) { Files.deleteIfExists(directory.resolve("keytool.log")); Files.deleteIfExists(directory); }
    }
    private void handshake(String expectedPin) throws Exception {
        ExecutorService worker = Executors.newSingleThreadExecutor();
        try (SSLServerSocket server = (SSLServerSocket) target.getServerSocketFactory().createServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            server.setSoTimeout(5000);
            Future<?> result = worker.submit(() -> {
                try (SSLSocket peer = (SSLSocket) server.accept()) {
                    peer.setSoTimeout(5000); peer.startHandshake(); peer.getOutputStream().write(42);
                } catch (IOException ignored) { /* Invalid-pin test deliberately aborts the handshake. */ }
            });
            try (SSLSocket client = (SSLSocket) Tls.client(expectedPin).getSocketFactory().createSocket(InetAddress.getLoopbackAddress(), server.getLocalPort())) {
                client.setSoTimeout(5000); client.startHandshake(); assertEquals(42, client.getInputStream().read());
            } finally { result.get(6, TimeUnit.SECONDS); }
        } finally { worker.shutdownNow(); }
    }
    @Test public void pinnedCertificateCanExchangeData() throws Exception { handshake(pin); }
    @Test public void wrongPinRejectsTls() throws Exception {
        try { handshake("00".repeat(32)); fail("wrong pin accepted"); }
        catch (SSLException expected) {}
    }
}
