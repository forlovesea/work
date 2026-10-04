import asyncio
import unittest
import argparse
from relay import Relay, relay_port, DEFAULT_PORT


class PortTests(unittest.TestCase):
    def test_allowed_range(self):
        self.assertEqual(DEFAULT_PORT, 55000)
        for port in (55000, 57500, 60000):
            self.assertEqual(relay_port(str(port)), port)

    def test_reject_outside_range(self):
        for value in ("80", "443", "54999", "60001", "65536", "-1", "bad"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                relay_port(value)


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.relay = Relay(wait_seconds=0.3, session_seconds=2)
        self.server = await asyncio.start_server(self.relay.handle, "127.0.0.1", 0, limit=4096)
        self.port = self.server.sockets[0].getsockname()[1]
        self.clients = []

    async def asyncTearDown(self):
        for _, writer in self.clients:
            writer.close()
            await writer.wait_closed()
        self.server.close()
        await self.server.wait_closed()
        for _ in range(50):
            if self.relay.connections == 0:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(self.relay.connections, 0)
        self.assertFalse(self.relay.rooms)

    async def client(self, role, room="a" * 32):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.clients.append((reader, writer))
        writer.write((role + " " + room + "\n").encode())
        await writer.drain()
        return reader, writer

    async def test_bidirectional_pairing_and_single_host(self):
        target, tw = await self.client("TARGET")
        self.assertEqual(await target.readline(), b"READY\n")
        host, hw = await self.client("HOST")
        self.assertEqual(await host.readline(), b"PAIRED\n")
        self.assertEqual(await target.readline(), b"PAIRED\n")
        payload = bytes(range(256)) * 1000
        tw.write(payload)
        await tw.drain()
        self.assertEqual(await asyncio.wait_for(host.readexactly(len(payload)), 1), payload)
        hw.write(b"control")
        await hw.drain()
        self.assertEqual(await target.readexactly(7), b"control")
        other, _ = await self.client("HOST")
        self.assertEqual(await other.readline(), b"ERROR unavailable\n")
        hw.close()
        self.assertEqual(await asyncio.wait_for(target.read(), 1), b"")

    async def test_unknown_room(self):
        reader, _ = await self.client("HOST")
        self.assertEqual(await reader.readline(), b"ERROR unavailable\n")

    async def test_duplicate_target(self):
        target, _ = await self.client("TARGET")
        self.assertEqual(await target.readline(), b"READY\n")
        other, _ = await self.client("TARGET")
        self.assertEqual(await other.readline(), b"ERROR duplicate\n")

    async def test_invalid_protocol(self):
        reader, _ = await self.client("ADMIN", "bad")
        self.assertEqual(await reader.readline(), b"ERROR protocol\n")

    async def test_wait_expiry(self):
        reader, _ = await self.client("TARGET")
        self.assertEqual(await reader.readline(), b"READY\n")
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")

    async def test_target_disconnect_removes_room(self):
        reader, writer = await self.client("TARGET")
        await reader.readline()
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.05)
        self.assertFalse(self.relay.rooms)

    async def test_capacity(self):
        self.relay.max_connections = 1
        reader, _ = await self.client("TARGET")
        await reader.readline()
        other, _ = await self.client("HOST")
        self.assertEqual(await other.readline(), b"ERROR capacity\n")


if __name__ == "__main__":
    unittest.main()
