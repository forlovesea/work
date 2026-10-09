#!/usr/bin/env python3
"""Python 3.8+ TLS rendezvous relay. Never decodes the inner screen/control TLS."""
import argparse
import asyncio
import contextlib
import logging
import re
import ssl
import json
import hmac
import secrets
from pathlib import Path

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
    def __init__(self, max_connections=256, wait_seconds=300, session_seconds=1800, access_key=None, presence_timeout=30):
        self.rooms = {}
        self.connections = 0
        self.max_connections = max_connections
        self.wait_seconds = wait_seconds
        self.session_seconds = session_seconds
        self.access_key = access_key
        self.presence_timeout = presence_timeout
        self.devices = {}
        self.shares = {}
        self.wake_timeout = 12

    async def json_send(self, writer, value):
        await self.send(writer, json.dumps(value, ensure_ascii=True, separators=(",", ":")))

    async def directory(self, reader, writer, line):
        request = json.loads(line)
        if not isinstance(request, dict):
            raise ValueError("request")
        supplied = request.get("key", "")
        if (not self.access_key or not isinstance(supplied, str)
                or not hmac.compare_digest(supplied.encode(), self.access_key.encode())):
            await self.json_send(writer, {"error": "unauthorized"})
            return
        operation = request.get("op")
        if operation == "LIST":
            result = []
            for device_id, device in self.devices.items():
                share = self.shares.get(device_id)
                state = "waiting" if share is None else "busy" if share["pair"].done() else "ready"
                result.append({"id": device_id, "name": device["name"], "state": state,
                               "wake": device["wake"]})
            await self.json_send(writer, {"devices": result})
            return
        device_id = request.get("id", "")
        if not isinstance(device_id, str) or not re.fullmatch(r"[0-9a-f]{32}", device_id):
            raise ValueError("device")
        if operation == "PRESENCE":
            name = request.get("name", "")
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60 or any(ord(c) < 32 for c in name):
                raise ValueError("name")
            device = {"name": name.strip(), "writer": writer,
                      "wake": request.get("wake") is True, "pending": None}
            old = self.devices.get(device_id)
            self.devices[device_id] = device
            if old:
                old["writer"].close()
            try:
                await self.json_send(writer, {"ok": True})
                while True:
                    beat = await asyncio.wait_for(reader.readline(), self.presence_timeout)
                    if beat != b"PING\n":
                        return
                    pending = device["pending"]
                    if pending is None:
                        await self.send(writer, "PONG")
                        continue
                    await self.send(writer, "WAKE " + pending[0])
                    answer = await asyncio.wait_for(reader.readline(), 5)
                    match = re.fullmatch(rb"WAKE_RESULT ([0-9a-f]{32}) (awake|blocked)\n", answer)
                    if not match or match[1].decode() != pending[0]:
                        return
                    if not pending[1].done():
                        pending[1].set_result({"status": match[2].decode()})
            finally:
                pending = device["pending"]
                if pending is not None and not pending[1].done():
                    pending[1].set_result({"error": "offline"})
                if self.devices.get(device_id) is device:
                    self.devices.pop(device_id, None)
            return
        if device_id not in self.devices:
            await self.json_send(writer, {"error": "offline"})
            return
        if operation == "WAKE":
            device = self.devices[device_id]
            if not device["wake"]:
                await self.json_send(writer, {"error": "wake_unsupported"})
                return
            if device["pending"] is not None:
                await self.json_send(writer, {"error": "wake_busy"})
                return
            pending = (secrets.token_hex(16), asyncio.get_running_loop().create_future())
            device["pending"] = pending
            try:
                try:
                    result = await asyncio.wait_for(asyncio.shield(pending[1]), self.wake_timeout)
                except asyncio.TimeoutError:
                    result = {"error": "wake_timeout"}
                await self.json_send(writer, result)
            finally:
                if device["pending"] is pending:
                    device["pending"] = None
                pending[1].cancel()
            return
        if operation == "SHARE":
            fingerprint, token = request.get("fingerprint", ""), request.get("token", "")
            if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint):
                raise ValueError("fingerprint")
            if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
                raise ValueError("token")
            if device_id in self.shares:
                await self.json_send(writer, {"error": "busy"})
                return
            loop = asyncio.get_running_loop()
            share = {"pair": loop.create_future(), "done": loop.create_future(),
                     "fingerprint": fingerprint, "token": token}
            self.shares[device_id] = share
            watcher = None
            try:
                await self.json_send(writer, {"ok": True})
                watcher = asyncio.create_task(reader.read(1))
                completed, _ = await asyncio.wait([share["pair"], watcher], timeout=self.wait_seconds,
                                                  return_when=asyncio.FIRST_COMPLETED)
                if watcher in completed or share["pair"] not in completed:
                    return
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
                peer = share["pair"].result()
                await self.send(writer, "PAIRED")
                await self.send(peer[1], "PAIRED")
                await self.tunnel((reader, writer), peer)
            finally:
                if self.shares.get(device_id) is share:
                    self.shares.pop(device_id, None)
                if watcher is not None:
                    watcher.cancel()
                    await asyncio.gather(watcher, return_exceptions=True)
                if not share["done"].done():
                    share["done"].set_result(None)
                if not share["pair"].done():
                    share["pair"].cancel()
            return
        if operation == "CONNECT":
            share = self.shares.get(device_id)
            if share is None or share["pair"].done():
                await self.json_send(writer, {"error": "unavailable"})
                return
            # Reserve before awaiting writes: only one Host can claim a share.
            share["pair"].set_result((reader, writer))
            # Prevent the SHARE handler from writing PAIRED before metadata.
            # writer.write queues the complete metadata before yielding in drain.
            writer.write((json.dumps({"fingerprint": share["fingerprint"], "token": share["token"]}) + "\n").encode("ascii"))
            await asyncio.wait_for(writer.drain(), 10)
            await asyncio.wait_for(asyncio.shield(share["done"]), self.session_seconds + 20)
            return
        raise ValueError("operation")

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
            if line.startswith(b"{"):
                await self.directory(reader, writer, line)
                return
            if self.access_key:
                await self.send(writer, "ERROR upgrade_required")
                return
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
    access_key = Path(args.access_key_file).read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", access_key):
        raise ValueError("access key file must contain 64 hexadecimal characters")
    relay = Relay(max_connections=args.max_connections, access_key=access_key)
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
    parser.add_argument("--access-key-file", default="/etc/remotecontrol/access.key")
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(main(options))
    except KeyboardInterrupt:
        pass
