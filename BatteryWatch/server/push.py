"""Optional Firebase delivery with durable retries, separate from ingestion."""
import asyncio
from contextlib import closing
import logging
import time


class InvalidToken(Exception):
    pass


class FirebaseSender:
    def __init__(self, config):
        import firebase_admin
        from firebase_admin import credentials, messaging
        self.messaging = messaging
        credential = credentials.Certificate(config['service_account']) if config.get('service_account') else credentials.ApplicationDefault()
        self.app = firebase_admin.initialize_app(credential, {'httpTimeout': 10}, name='batterywatch')

    def send(self, token, event):
        m = self.messaging
        data = {k: str(event[k]) for k in ('event_id', 'site_id', 'device_id', 'transition', 'message')}
        try:
            m.send(m.Message(token=token, data=data,
                notification=m.Notification(title=f"{event['site_id']}/{event['device_id']}: {event['transition']}", body=event['message']),
                android=m.AndroidConfig(priority='high', ttl=3600,
                    notification=m.AndroidNotification(channel_id='battery_alarms', tag=event['event_id']))), app=self.app)
        except m.UnregisteredError as exc:
            raise InvalidToken() from exc


class Dispatcher:
    def __init__(self, storage, config, sender):
        self.storage, self.config, self.sender = storage, config, sender

    def tick(self, now=None):
        now = time.time() if now is None else now
        with closing(self.storage.connect()) as db:
            rows = db.execute('''SELECT q.*,p.token,p.viewer_id,e.site_id,e.device_id,e.transition,e.message
                FROM push_outbox q JOIN push_devices p USING(installation_id) JOIN alarm_events e USING(event_id)
                WHERE q.sent_at IS NULL AND q.next_attempt<=? ORDER BY q.next_attempt LIMIT 20''', (now,)).fetchall()
        for row in rows:
            event = dict(row)
            viewer = next((v for v in (self.config.get('api') or {}).get('viewers', []) if v['id'] == event['viewer_id']), None)
            granted = viewer and dict(site_id=event['site_id'], device_id=event['device_id']) in viewer['devices']
            result, error = None, None
            if not granted:
                result = 'revoked'
            else:
                try:
                    self.sender.send(event['token'], event)
                    result = 'sent'
                except InvalidToken:
                    result = 'invalid_token'
                except Exception as exc:
                    # Never persist provider exception text containing credentials.
                    error = type(exc).__name__
            with self.storage.lock, closing(self.storage.connect()) as db, db:
                if result == 'invalid_token':
                    db.execute('DELETE FROM push_devices WHERE installation_id=? AND token=?', (event['installation_id'], event['token']))
                if result:
                    db.execute('UPDATE push_outbox SET sent_at=?,last_error=? WHERE event_id=? AND installation_id=?',
                               (now, None if result == 'sent' else result, event['event_id'], event['installation_id']))
                else:
                    delay = min(3600, 5 * 2 ** min(event['attempts'], 10))
                    db.execute('UPDATE push_outbox SET attempts=attempts+1,next_attempt=?,last_error=? WHERE event_id=? AND installation_id=?',
                               (now + delay, error, event['event_id'], event['installation_id']))


async def deliver(dispatcher, stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(dispatcher.tick)
        except Exception:
            logging.exception('Push delivery worker failed; queue retained')
        try:
            await asyncio.wait_for(stop.wait(), 2)
        except asyncio.TimeoutError:
            pass
