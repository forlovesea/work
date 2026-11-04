"""Exercise PHP's real SMTP transport against local TLS servers; sends no external mail.

Usage: python bin/test-approval-smtp.py /path/to/php /path/to/openssl
"""
import base64
import email
from email import policy
import os
from pathlib import Path
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading


class SMTP(socketserver.StreamRequestHandler):
    def handle(self):
        encrypted = self.server.implicit
        self.wfile.write(b'220 localhost\r\n')
        while True:
            line = self.rfile.readline().strip()
            if not line:
                return
            command = line.split(b' ', 1)[0].upper()
            if command == b'EHLO':
                self.wfile.write(b'250-localhost\r\n250-STARTTLS\r\n250 AUTH PLAIN\r\n')
            elif command == b'STARTTLS':
                self.wfile.write(b'220 begin TLS\r\n')
                try:
                    self.connection = self.server.tls.wrap_socket(self.connection, server_side=True)
                except (ssl.SSLError, ConnectionAbortedError, ConnectionResetError):
                    return  # Expected in the untrusted-certificate test.
                self.rfile = self.connection.makefile('rb')
                self.wfile = self.connection.makefile('wb', buffering=0)
                encrypted = True
            elif command == b'AUTH':
                assert encrypted, 'Credentials sent without TLS'
                pieces = line.split()
                if len(pieces) < 3:
                    self.wfile.write(b'334 \r\n')
                    credential = self.rfile.readline().strip()
                else:
                    credential = pieces[2]
                assert base64.b64decode(credential).endswith(b'\x00sender@example.invalid\x00test-password')
                self.server.authenticated = True
                self.wfile.write(b'235 authenticated\r\n')
            elif command == b'DATA':
                assert self.server.authenticated
                self.wfile.write(b'354 data\r\n')
                chunks = []
                while True:
                    line = self.rfile.readline()
                    if line == b'.\r\n' or not line:
                        break
                    chunks.append(line)
                self.server.message = email.message_from_bytes(b''.join(chunks), policy=policy.default)
                self.wfile.write(b'250 accepted\r\n')
            elif command == b'QUIT':
                self.wfile.write(b'221 bye\r\n')
                return
            else:
                self.wfile.write(b'250 OK\r\n')


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        if self.implicit:
            connection = self.tls.wrap_socket(connection, server_side=True)
        return connection, address


def main():
    php, openssl = map(lambda value: str(Path(value).resolve()), sys.argv[1:3])
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='approval-smtp-test-') as temporary:
        directory = Path(temporary)
        key, certificate = directory / 'key.pem', directory / 'certificate.pem'
        subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key), '-out', str(certificate),
                        '-days', '1', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                       check=True, capture_output=True)
        script = directory / 'send.php'
        script.write_text("<?php require " + repr((root / 'lib' / 'approval-mail.php').as_posix()) + ";\n"
                          "$config = approvalMailConfig(); echo sendApprovalMail($config, 'forlovesea@gmail.com', '테스트', '테스트 본문') ? 'sent' : 'failed';", encoding='utf-8')
        for security, trusted in [('starttls', True), ('ssl', True), ('starttls', False)]:
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(certificate, key)
            with Server(('127.0.0.1', 0), SMTP) as server:
                server.tls, server.implicit = tls, security == 'ssl'
                server.authenticated, server.message = False, None
                threading.Thread(target=server.serve_forever, daemon=True).start()
                env = dict(os.environ, PUBLIC_BASE_URL='https://example.invalid/installed-management', SMTP_HOST='localhost',
                           SMTP_PORT=str(server.server_address[1]), SMTP_SECURITY=security,
                           SMTP_USERNAME='sender@example.invalid', SMTP_PASSWORD='test-password', SMTP_FROM='sender@example.invalid')
                flags = [php]
                if os.name == 'nt':
                    flags += ['-d', 'extension_dir=' + str(Path(php).parent / 'ext'), '-d', 'extension=curl']
                if trusted:
                    flags += ['-d', 'curl.cainfo=' + str(certificate)]
                result = subprocess.run(flags + [str(script)], env=env, capture_output=True, text=True, timeout=25)
                assert result.returncode == 0, result.stderr
                assert result.stdout == ('sent' if trusted else 'failed'), result.stdout
                if trusted:
                    assert server.authenticated
                    assert server.message['To'] == 'forlovesea@gmail.com'
                    assert server.message.get_content().strip() == '테스트 본문'
                else:
                    assert not server.authenticated and server.message is None
                server.shutdown()
        print('PASS: authenticated STARTTLS/SSL, UTF-8 message, fixed recipient and untrusted certificate refusal')


if __name__ == '__main__':
    main()
