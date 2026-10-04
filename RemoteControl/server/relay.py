#!/usr/bin/env python3
"""Python 3.8+ TLS rendezvous relay. Never decodes the inner screen/control TLS."""
import argparse
import asyncio
import contextlib
import logging
import re
import ssl

DEFAULT_PORT = 55000
MIN_PORT, MAX_PORT = 55000, 60000


def relay_port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer between 55000 and 60000")
    if not MIN_PORT <= port <= MAX_PORT:
        raise argparse.ArgumentTypeError("port must be between 55000 and 60000")
    return port


class Relay:
    def __init__(self, max_connections=256, wait_seconds=300, session_seconds=1800):
        self.rooms = {}
        self.connections = 0
        self.max_connections = max_connections
        self.wait_seconds = wait_seconds
        self.session_seconds = session_seconds

    async def send(self, writer, text):
        writer.write(text.encode("ascii") + b"\n")
        await asyncio.wait_for(writer.drain(), 10)

    async def pump(self, reader, writer):
        while True:
            data = await reader.read(16384)
            if not data:
                return
            writer.write(data)
            await asyncio.wait_for(writer.drain(), 30)

    async def tunnel(self, left, right):
        tasks = [asyncio.create_task(self.pump(left[0], right[1])),
                 asyncio.create_task(self.pump(right[0], left[1]))]
        try:
            done, _ = await asyncio.wait(tasks, timeout=self.session_seconds,
                                         return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def handle(self, reader, writer):
        self.connections += 1
        room = None
        pair = None
        done = None
        watcher = None
        try:
            if self.connections > self.max_connections:
                await self.send(writer, "ERROR capacity")
                return
            line = await asyncio.wait_for(reader.readline(), 10)
            match = re.fullmatch(rb"(TARGET|HOST) ([0-9a-f]{32})\n", line)
            if not match:
                await self.send(writer, "ERROR protocol")
                return
            role, room = match.group(1), match.group(2)
            if role == b"TARGET":
                if room in self.rooms:
                    await self.send(writer, "ERROR duplicate")
                    return
                pair = asyncio.get_running_loop().create_future()
                done = asyncio.get_running_loop().create_future()
                self.rooms[room] = (pair, done)
                await self.send(writer, "READY")
                watcher = asyncio.create_task(reader.read(1))
                completed, _ = await asyncio.wait([pair, watcher], timeout=self.wait_seconds,
                                                 return_when=asyncio.FIRST_COMPLETED)
                if watcher in completed or pair not in completed:
                    return
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
                peer = pair.result()
                await self.send(writer, "PAIRED")
                await self.send(peer[1], "PAIRED")
                await self.tunnel((reader, writer), peer)
            else:
                entry = self.rooms.pop(room, None)
                if entry is None:
                    await self.send(writer, "ERROR unavailable")
                    return
                host_pair, host_done = entry
                if host_pair.done():
                    await self.send(writer, "ERROR unavailable")
                    return
                host_pair.set_result((reader, writer))
                await asyncio.wait_for(asyncio.shield(host_done), self.session_seconds + 20)
        except (asyncio.TimeoutError, ConnectionError, OSError, ValueError):
            # Never log invitations, tokens, or payloads.
            pass
        finally:
            if room is not None and pair is not None and self.rooms.get(room, (None,))[0] is pair:
                self.rooms.pop(room, None)
            if watcher is not None:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            if done is not None and not done.done():
                done.set_result(None)
            if pair is not None and not pair.done():
                pair.cancel()
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), 3)
            self.connections -= 1


async def main(args):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    relay = Relay(max_connections=args.max_connections)
    server = await asyncio.start_server(relay.handle, args.bind, args.port, ssl=context,
                                        ssl_handshake_timeout=10, limit=4096)
    logging.info("TLS relay listening on %s:%s", args.bind, args.port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=relay_port, default=DEFAULT_PORT,
                        help="relay TCP port: 55000-60000 (default: 55000)")
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--max-connections", type=int, default=256)
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(main(options))
    except KeyboardInterrupt:
        pass
