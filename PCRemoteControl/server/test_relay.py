import asyncio
import json
import struct
import unittest
from relay import Relay, read_message

class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.relay = Relay('jjh1234')
        self.server = await asyncio.start_server(self.relay.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.writers = []

    async def asyncTearDown(self):
        for w in self.writers:
            w.close()
        await asyncio.gather(*(w.wait_closed() for w in self.writers), return_exceptions=True)
        self.server.close()
        await self.server.wait_closed()
        await asyncio.sleep(0.05)

    async def send(self, w, value):
        data = json.dumps(value).encode()
        w.write(struct.pack('!I', len(data)) + data)
        await w.drain()

    async def peer(self, role, password='jjh1234', id='test'):
        r, w = await asyncio.open_connection('127.0.0.1', self.port)
        self.writers.append(w)
        await self.send(w, dict(type='hello', role=role, password=password, id=id, name='Test PC'))
        return r, w, await read_message(r, 2)

    async def test_authentication_and_duplicate_id(self):
        _, _, reply = await self.peer('host', 'wrong')
        self.assertEqual(reply['type'], 'error')
        _, _, reply = await self.peer('target')
        self.assertEqual(reply['type'], 'ok')
        _, _, reply = await self.peer('target')
        self.assertEqual(reply['type'], 'error')

    async def test_pair_frames_input_busy_and_disconnect(self):
        tr, tw, _ = await self.peer('target')
        hr, hw, _ = await self.peer('host')
        r2, w2, _ = await self.peer('host')
        await self.send(hw, dict(type='list'))
        self.assertEqual((await read_message(hr))['targets'][0]['state'], 'ready')
        await self.send(hw, dict(type='connect', id='test'))
        self.assertEqual((await read_message(hr))['type'], 'paired')
        self.assertEqual((await read_message(tr))['type'], 'paired')
        await self.send(w2, dict(type='connect', id='test'))
        self.assertEqual((await read_message(r2))['type'], 'error')
        frame = dict(type='frame', data='AQID')
        await self.send(tw, frame)
        self.assertEqual(await read_message(hr), frame)
        command = dict(type='input', action='key', key=65, down=True)
        await self.send(hw, command)
        self.assertEqual(await read_message(tr), command)
        await self.send(hw, dict(type='disconnect'))
        self.assertEqual((await read_message(tr))['type'], 'ended')
        self.assertEqual((await read_message(hr))['type'], 'ended')
        await self.send(tw, dict(type='ping'))
        self.assertEqual((await read_message(tr))['type'], 'pong')
        await self.send(hw, dict(type='list'))
        self.assertEqual((await read_message(hr))['targets'][0]['state'], 'ready')

    async def test_target_socket_close_removes_listing(self):
        _, tw, _ = await self.peer('target')
        hr, hw, _ = await self.peer('host')
        tw.close()
        await tw.wait_closed()
        await asyncio.sleep(0.05)
        await self.send(hw, dict(type='list'))
        self.assertEqual((await read_message(hr))['targets'], [])

    async def test_invalid_length_is_closed(self):
        r, w, _ = await self.peer('host')
        w.write(struct.pack('!I', 9 * 1024 * 1024))
        await w.drain()
        self.assertEqual(await asyncio.wait_for(r.read(), 2), b'')

if __name__ == '__main__':
    unittest.main()
