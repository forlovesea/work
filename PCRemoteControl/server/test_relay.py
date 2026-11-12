import asyncio
import json
import struct
import unittest
from unittest.mock import patch
from relay import Relay, read_message, send_auth_email

class MailTests(unittest.TestCase):
    def test_smtp_uses_tls_and_fixed_recipient(self):
        settings = dict(PCREMOTE_SMTP_HOST='smtp.example.com', PCREMOTE_SMTP_USER='sender@example.com', PCREMOTE_SMTP_PASSWORD='test-secret')
        with patch.dict('os.environ', settings, clear=True), patch('relay.smtplib.SMTP') as smtp:
            send_auth_email('012345')
            client = smtp.return_value.__enter__.return_value
            client.starttls.assert_called_once()
            client.login.assert_called_once_with('sender@example.com', 'test-secret')
            message = client.send_message.call_args[0][0]
            self.assertEqual(message['To'], 'forlovesea@gmail.com')
            self.assertIn('012345', message.get_content())
            self.assertLess([call[0] for call in client.mock_calls].index('starttls'), [call[0] for call in client.mock_calls].index('login'))

    def test_missing_smtp_configuration_fails_closed(self):
        with patch.dict('os.environ', {}, clear=True), patch('relay.smtplib.SMTP') as smtp:
            with self.assertRaises(ValueError):
                send_auth_email('012345')
            smtp.assert_not_called()

class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.codes = []
        self.relay = Relay('jjh1234', self.codes.append)
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

    async def peer(self, role, password='jjh1234', id='test', verify=True, reset_limit=True):
        if reset_limit:
            self.relay.mail_times.clear()
            self.relay.last_mail = float('-inf')
        r, w = await asyncio.open_connection('127.0.0.1', self.port)
        self.writers.append(w)
        await self.send(w, dict(type='hello', role=role, password=password, id=id, name='Test PC'))
        reply = await read_message(r, 2)
        if verify and reply['type'] == 'email_required':
            await self.send(w, dict(type='verify_email', code=self.codes[-1]))
            reply = await read_message(r, 2)
        return r, w, reply

    async def test_password_failure_sends_no_mail(self):
        _, _, reply = await self.peer('host', 'wrong')
        self.assertEqual(reply['type'], 'error')
        self.assertEqual(self.codes, [])

    async def test_email_required_before_target_registration(self):
        r, w, reply = await self.peer('target', verify=False)
        self.assertEqual(reply['email'], 'forlovesea@gmail.com')
        self.assertEqual(self.relay.targets, {})
        await self.send(w, dict(type='verify_email', code=self.codes[-1]))
        self.assertEqual((await read_message(r))['type'], 'ok')
        self.assertIn('test', self.relay.targets)

    async def test_wrong_code_and_pre_auth_operations_are_rejected(self):
        for message in [dict(type='verify_email', code='invalid'), dict(type='list'), dict(type='connect', id='test')]:
            r, w, _ = await self.peer('host', verify=False)
            await self.send(w, message)
            self.assertEqual((await read_message(r))['type'], 'error')
            self.assertEqual(await r.read(), b'')

    async def test_code_cannot_be_reused_on_another_connection(self):
        await self.peer('host')
        old_code = self.codes[-1]
        with patch('relay.secrets.randbelow', return_value=(int(old_code) + 1) % 1000000):
            r, w, _ = await self.peer('host', verify=False)
        await self.send(w, dict(type='verify_email', code=old_code))
        self.assertEqual((await read_message(r))['type'], 'error')

    async def test_expired_code_closes_connection(self):
        with patch('relay.AUTH_SECONDS', 0.05):
            r, _, _ = await self.peer('target', verify=False)
            self.assertEqual(await asyncio.wait_for(r.read(), 2), b'')
        self.assertEqual(self.relay.targets, {})

    async def test_mail_rate_limit(self):
        await self.peer('host')
        _, _, reply = await self.peer('host', reset_limit=False)
        self.assertEqual(reply['type'], 'error')
        self.assertEqual(len(self.codes), 1)

    async def test_mail_failure_denies_connection(self):
        def fail(code):
            raise OSError('SMTP unavailable')
        self.relay.mail_sender = fail
        _, _, reply = await self.peer('target')
        self.assertEqual(reply['type'], 'error')
        self.assertEqual(self.relay.targets, {})

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

    async def test_webrtc_signaling_is_forwarded_only_between_paired_roles(self):
        tr, tw, _ = await self.peer('target')
        hr, hw, _ = await self.peer('host')
        await self.send(hw, dict(type='connect', id='test'))
        await read_message(hr)
        await read_message(tr)
        session = '0123456789abcdef0123456789abcdef'
        offer = dict(type='rtc', action='offer', session=session, description='offer sdp')
        await self.send(hw, offer)
        self.assertEqual(await read_message(tr), offer)
        answer = dict(type='rtc', action='answer', session=session, description='answer sdp')
        await self.send(tw, answer)
        self.assertEqual(await read_message(hr), answer)
        candidate = dict(type='rtc', action='candidate', session=session,
                         candidate=dict(candidate='candidate:1 1 UDP 1 192.0.2.1 5000 typ host',
                                        sdpMid='video', sdpMLineIndex=0))
        await self.send(tw, candidate)
        self.assertEqual(await read_message(hr), candidate)

    async def test_invalid_webrtc_signal_logs_reason_without_payload(self):
        tr, tw, _ = await self.peer('target')
        hr, hw, _ = await self.peer('host')
        await self.send(hw, dict(type='connect', id='test'))
        await read_message(hr)
        await read_message(tr)

        with patch('builtins.print') as log:
            await self.send(hw, dict(
                type='rtc', action='offer', session='invalid',
                description='private test description'
            ))
            self.assertEqual(await asyncio.wait_for(hr.read(), 2), b'')
            await asyncio.sleep(0.05)

        output = ' '.join(str(call.args[0]) for call in log.call_args_list)
        self.assertIn('role=host operation=rtc error=ValueError: Invalid WebRTC session', output)
        self.assertNotIn('private test description', output)

    async def test_webrtc_offer_from_target_is_rejected(self):
        tr, tw, _ = await self.peer('target')
        await self.send(tw, dict(type='rtc', action='offer',
                                 session='0123456789abcdef0123456789abcdef',
                                 description='offer sdp'))
        self.assertEqual(await asyncio.wait_for(tr.read(), 2), b'')

    async def test_capture_error_and_large_frame_recovery(self):
        import base64
        tr, tw, _ = await self.peer('target')
        hr, hw, _ = await self.peer('host')
        await self.send(hw, dict(type='connect', id='test'))
        await read_message(hr)
        await read_message(tr)
        failure = dict(type='frame', data='', capture_error='Desktop is locked')
        await self.send(tw, failure)
        self.assertEqual(await read_message(hr), failure)
        # Exercise a payload larger than the stream reader buffer and subsequent recovery.
        frame = dict(type='frame', data=base64.b64encode(bytes(range(256)) * 2048).decode(), nearly_black=False)
        await self.send(tw, frame)
        self.assertEqual(await read_message(hr), frame)
        await self.send(hw, dict(type='input', action='release'))
        self.assertEqual((await read_message(tr))['action'], 'release')
        await self.send(hw, dict(type='ping'))
        self.assertEqual((await read_message(hr))['type'], 'pong')

    async def test_invalid_length_is_closed(self):
        r, w, _ = await self.peer('host')
        w.write(struct.pack('!I', 9 * 1024 * 1024))
        await w.drain()
        self.assertEqual(await asyncio.wait_for(r.read(), 2), b'')

if __name__ == '__main__':
    unittest.main()
