"""Local protocol test receiver, not a production/public server."""
import argparse
import hmac
import os
import socketserver
import sqlite3
import json
from upload_transport import encode_frame, receive_frame, utc_now


class Receiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, database, token):
        self.database, self.token = str(database), token
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS samples (sample_id TEXT PRIMARY KEY, received_at TEXT, payload TEXT)')
        super().__init__(address, Handler)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            while True:
                message = receive_frame(self.request)
                token = message.get('token')
                if message.get('type') != 'upload' or not isinstance(token, str) or not hmac.compare_digest(token, self.server.token):
                    return
                payload = message['payload']
                sample_id = payload['sample_id']
                if not isinstance(sample_id, str) or not sample_id:
                    return
                with sqlite3.connect(self.server.database) as db:
                    db.execute('INSERT OR IGNORE INTO samples VALUES(?,?,?)',
                               (sample_id, utc_now(), json.dumps(payload, ensure_ascii=False)))
                # ACK only after transaction commit.
                self.request.sendall(encode_frame({'type':'ack','sample_id':sample_id,'ok':True}))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9443)
    parser.add_argument('--database', default='receiver.sqlite3')
    args = parser.parse_args()
    token = os.environ.get('BATTERYWATCH_TEST_TOKEN')
    if not token:
        parser.error('Set BATTERYWATCH_TEST_TOKEN first')
    with Receiver(('127.0.0.1', args.port), args.database, token) as server:
        print('Local plain TCP test receiver:', server.server_address, flush=True)
        server.serve_forever()
