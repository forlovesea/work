"""PCRemoteControl relay. Python 3.8+, standard library only."""
import argparse
import asyncio
import hmac
import json
import os
import ssl
import struct
import time

MAX_MESSAGE = 8 * 1024 * 1024

async def read_message(reader, timeout=35):
    async def read():
        size = struct.unpack('!I', await reader.readexactly(4))[0]
        if not 0 < size <= MAX_MESSAGE:
            raise ValueError('Invalid message size')
        value = json.loads(await reader.readexactly(size))
        if not isinstance(value, dict):
            raise ValueError('Expected object')
        return value
    return await asyncio.wait_for(read(), timeout)

class Peer:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.lock = asyncio.Lock()
        self.role = self.id = self.name = ''
        self.other = None

    async def send(self, value):
        raw = json.dumps(value, separators=(',', ':')).encode()
        if len(raw) > MAX_MESSAGE:
            raise ValueError('Message too large')
        async with self.lock:
            self.writer.write(struct.pack('!I', len(raw)) + raw)
            await asyncio.wait_for(self.writer.drain(), 10)

class Relay:
    def __init__(self, password):
        self.password = password
        self.targets = {}
        self.peers = set()
        self.failures = {}

    async def detach(self, peer):
        other = peer.other
        peer.other = None
        if other and other.other is peer:
            other.other = None
            try:
                await other.send({'type': 'ended'})
            except (OSError, asyncio.TimeoutError):
                other.writer.close()

    async def handle(self, reader, writer):
        p = Peer(reader, writer)
        address = writer.get_extra_info('peername')[0]
        if len(self.peers) >= 256:
            writer.close()
            return
        self.peers.add(p)
        try:
            now = time.monotonic()
            self.failures = {ip: entry for ip, entry in self.failures.items() if now - entry[1] < 60}
            if self.failures.get(address, (0, 0))[0] >= 10:
                await p.send({'type': 'error', 'message': 'Too many attempts; wait 60 seconds.'})
                return
            hello = await read_message(reader, 10)
            password = hello.get('password')
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.password.encode()):
                count = self.failures.get(address, (0, now))[0]
                self.failures[address] = (count + 1, now)
                await p.send({'type': 'error', 'message': 'Authentication failed'})
                return
            p.role = hello.get('role')
            if hello.get('type') != 'hello' or p.role not in ('target', 'host'):
                raise ValueError('Invalid hello')
            if p.role == 'target':
                p.id, p.name = hello.get('id'), hello.get('name')
                if not isinstance(p.id, str) or not 1 <= len(p.id) <= 80 or not isinstance(p.name, str) or not 1 <= len(p.name) <= 80:
                    raise ValueError('Invalid target identity')
                if p.id in self.targets:
                    await p.send({'type': 'error', 'message': 'Target ID already online'})
                    return
                self.targets[p.id] = p
            await p.send({'type': 'ok'})
            while True:
                m = await read_message(reader)
                kind = m.get('type')
                if kind == 'ping':
                    await p.send({'type': 'pong'})
                elif kind == 'list' and p.role == 'host':
                    await p.send({'type': 'targets', 'targets': [
                        {'id': t.id, 'name': t.name, 'state': 'busy' if t.other else 'ready'}
                        for t in self.targets.values()]})
                elif kind == 'connect' and p.role == 'host':
                    t = self.targets.get(m.get('id'))
                    if p.other or not t or t.other:
                        await p.send({'type': 'error', 'message': 'Target unavailable or busy'})
                        continue
                    p.other, t.other = t, p
                    await p.send({'type': 'paired', 'name': t.name})
                    await t.send({'type': 'paired'})
                elif kind == 'disconnect':
                    await self.detach(p)
                    await p.send({'type': 'ended'})
                elif kind == 'frame' and p.role == 'target' and p.other:
                    await p.other.send(m)
                elif kind == 'input' and p.role == 'host' and p.other:
                    await p.other.send(m)
                else:
                    # Late frames/input after disconnect are harmless and discarded.
                    if kind not in ('frame', 'input'):
                        raise ValueError('Unsupported operation')
        except (OSError, ValueError, TypeError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            pass
        finally:
            if self.targets.get(p.id) is p:
                del self.targets[p.id]
            await self.detach(p)
            self.peers.discard(p)
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, asyncio.TimeoutError):
                pass

async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=61000)
    parser.add_argument('--cert', required=True)
    parser.add_argument('--key', required=True)
    args = parser.parse_args()
    if 55000 <= args.port <= 60000:
        parser.error('55000-60000 is reserved for the existing smartphone RemoteControl.')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    relay = Relay(os.environ.get('PCREMOTE_PASSWORD', 'jjh1234'))
    server = await asyncio.start_server(relay.handle, args.bind, args.port, ssl=context, ssl_handshake_timeout=10)
    print('PCRemoteControl TLS relay listening on port', args.port, flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
