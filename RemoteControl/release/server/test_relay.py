import asyncio
import unittest
import argparse
import json
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

    async def test_reconnect_same_room_after_disconnect(self):
        reader, writer = await self.client("TARGET")
        self.assertEqual(await reader.readline(), b"READY\n")
        writer.close()
        await writer.wait_closed()
        for _ in range(50):
            if not self.relay.rooms:
                break
            await asyncio.sleep(0.01)
        target, _ = await self.client("TARGET")
        self.assertEqual(await target.readline(), b"READY\n")
        host, hw = await self.client("HOST")
        self.assertEqual(await host.readline(), b"PAIRED\n")
        self.assertEqual(await target.readline(), b"PAIRED\n")
        hw.write(b"reconnected")
        await hw.drain()
        self.assertEqual(await asyncio.wait_for(target.readexactly(11), 1), b"reconnected")


class DirectoryTests(unittest.IsolatedAsyncioTestCase):
    key = "c" * 64
    device = "d" * 32
    fingerprint = "f" * 64
    token = "a" * 32

    async def asyncSetUp(self):
        await RelayTests.asyncSetUp(self)
        self.relay.access_key = self.key

    asyncTearDown = RelayTests.asyncTearDown

    async def request(self, op, **fields):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.clients.append((reader, writer))
        data = dict(op=op, key=self.key, id=self.device)
        data.update(fields)
        writer.write(json.dumps(data).encode() + b"\n")
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), 1))
        return reader, writer, response

    async def presence(self):
        reader, writer, response = await self.request("PRESENCE", name="업무폰")
        self.assertEqual(response, {"ok": True})
        return reader, writer

    async def share(self):
        reader, writer, response = await self.request("SHARE", fingerprint=self.fingerprint, token=self.token)
        self.assertEqual(response, {"ok": True})
        return reader, writer

    async def test_authenticated_list_states_and_no_secrets(self):
        await self.presence()
        _, _, response = await self.request("LIST")
        self.assertEqual(response["devices"], [{"id": self.device, "name": "업무폰", "state": "waiting", "wake": False}])
        target, _ = await self.share()
        _, _, response = await self.request("LIST")
        self.assertEqual(response["devices"][0]["state"], "ready")
        self.assertNotIn("token", json.dumps(response))
        host, _, selected = await self.request("CONNECT")
        self.assertEqual(selected, {"fingerprint": self.fingerprint, "token": self.token})
        self.assertEqual(await host.readline(), b"PAIRED\n")
        self.assertEqual(await target.readline(), b"PAIRED\n")
        _, _, response = await self.request("LIST")
        self.assertEqual(response["devices"][0]["state"], "busy")

    async def test_unauthorized_operations_and_legacy_rejected(self):
        for op in ("LIST", "PRESENCE", "SHARE", "CONNECT", "WAKE"):
            _, _, response = await self.request(op, key="bad")
            self.assertEqual(response, {"error": "unauthorized"})
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.clients.append((reader, writer))
        writer.write(b"TARGET " + b"a" * 32 + b"\n")
        await writer.drain()
        self.assertEqual(await reader.readline(), b"ERROR upgrade_required\n")
        self.assertFalse(self.relay.devices)
        self.assertFalse(self.relay.shares)

    async def test_heartbeat_and_offline_removal(self):
        reader, writer = await self.presence()
        writer.write(b"PING\n"); await writer.drain()
        self.assertEqual(await reader.readline(), b"PONG\n")
        writer.close(); await writer.wait_closed()
        for _ in range(50):
            if not self.relay.devices:
                break
            await asyncio.sleep(0.01)
        _, _, response = await self.request("LIST")
        self.assertEqual(response, {"devices": []})

    async def test_heartbeat_timeout(self):
        self.relay.presence_timeout = 0.05
        reader, _ = await self.presence()
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        self.assertFalse(self.relay.devices)

    async def test_presence_reconnect_does_not_remove_new_registration(self):
        old, _ = await self.presence()
        new, nw = await self.presence()
        self.assertEqual(await asyncio.wait_for(old.read(), 1), b"")
        nw.write(b"PING\n"); await nw.drain()
        self.assertEqual(await new.readline(), b"PONG\n")
        _, _, response = await self.request("LIST")
        self.assertEqual(len(response["devices"]), 1)

    async def test_single_host_tunnel_and_share_cleanup(self):
        await self.presence()
        target, tw = await self.share()
        results = await asyncio.gather(self.request("CONNECT"), self.request("CONNECT"))
        accepted = [r for r in results if "token" in r[2]]
        rejected = [r for r in results if r[2].get("error") == "unavailable"]
        self.assertEqual(len(accepted), 1); self.assertEqual(len(rejected), 1)
        host, hw, _ = accepted[0]
        self.assertEqual(await host.readline(), b"PAIRED\n")
        self.assertEqual(await target.readline(), b"PAIRED\n")
        tw.write(b"screen"); await tw.drain()
        self.assertEqual(await asyncio.wait_for(host.readexactly(6), 1), b"screen")
        hw.write(b"touch"); await hw.drain()
        self.assertEqual(await asyncio.wait_for(target.readexactly(5), 1), b"touch")
        hw.close(); await hw.wait_closed()
        self.assertEqual(await asyncio.wait_for(target.read(), 1), b"")
        self.assertFalse(self.relay.shares)
        _, _, response = await self.request("CONNECT")
        self.assertEqual(response, {"error": "unavailable"})
        await self.share()

    async def test_unapproved_and_offline_not_connectable(self):
        _, _, response = await self.request("CONNECT")
        self.assertEqual(response, {"error": "offline"})
        await self.presence()
        _, _, response = await self.request("CONNECT")
        self.assertEqual(response, {"error": "unavailable"})

    async def wait_pending(self):
        for _ in range(100):
            if self.relay.devices[self.device]["pending"] is not None:
                return
            await asyncio.sleep(0.001)
        self.fail("wake not queued")

    async def test_wake_without_share_and_confirmed_results(self):
        target, tw, _ = await self.request("PRESENCE", name="Target", wake=True)
        for result in ("awake", "blocked"):
            pending = asyncio.create_task(self.request("WAKE"))
            await self.wait_pending()
            _, _, duplicate = await self.request("WAKE")
            self.assertEqual(duplicate, {"error": "wake_busy"})
            tw.write(b"PING\n"); await tw.drain()
            command = await asyncio.wait_for(target.readline(), 1)
            self.assertTrue(command.startswith(b"WAKE "))
            self.assertFalse(pending.done())
            tw.write(b"WAKE_RESULT " + command.split()[1] + b" " + result.encode() + b"\n")
            await tw.drain()
            self.assertEqual((await pending)[2], {"status": result})
            tw.write(b"PING\n"); await tw.drain()
            self.assertEqual(await target.readline(), b"PONG\n")
        self.assertFalse(self.relay.shares)

    async def test_wake_offline_and_old_target(self):
        self.assertEqual((await self.request("WAKE"))[2], {"error": "offline"})
        await self.presence()
        self.assertEqual((await self.request("WAKE"))[2], {"error": "wake_unsupported"})

    async def test_wake_timeout_discards_undelivered_command(self):
        self.relay.wake_timeout = 0.03
        target, tw, _ = await self.request("PRESENCE", name="Target", wake=True)
        self.assertEqual((await self.request("WAKE"))[2], {"error": "wake_timeout"})
        tw.write(b"PING\n"); await tw.drain()
        self.assertEqual(await target.readline(), b"PONG\n")
        self.assertIsNone(self.relay.devices[self.device]["pending"])

    async def test_wake_disconnect_and_invalid_ack(self):
        for invalid_ack in (False, True):
            target, tw, _ = await self.request("PRESENCE", name="Target", wake=True)
            pending = asyncio.create_task(self.request("WAKE"))
            await self.wait_pending()
            if invalid_ack:
                tw.write(b"PING\n"); await tw.drain()
                await target.readline()
                tw.write(b"WAKE_RESULT wrong awake\n"); await tw.drain()
            else:
                tw.close(); await tw.wait_closed()
            self.assertEqual((await pending)[2], {"error": "offline"})

    async def test_share_timeout_returns_to_waiting(self):
        await self.presence()
        target, _ = await self.share()
        self.assertEqual(await asyncio.wait_for(target.read(), 1), b"")
        _, _, response = await self.request("LIST")
        self.assertEqual(response["devices"][0]["state"], "waiting")


if __name__ == "__main__":
    unittest.main()
