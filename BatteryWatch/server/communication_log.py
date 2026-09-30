"""Directional, credential-free logging and local runtime debug control."""
import asyncio
import json
import logging
from pathlib import Path
import os
import tempfile


class PeerLog(logging.LoggerAdapter):
    def __init__(self, logger, writer, kind):
        peer = writer.get_extra_info('peername')
        address = str(peer[0]) if isinstance(peer, tuple) and peer else 'unknown'
        super().__init__(logger, {'endpoint': kind + '(' + address + ')'})

    def process(self, message, kwargs):
        outgoing = message.startswith(('API response', 'UPLOAD ack'))
        descriptions = [('API request ', '조회 요청 수신'), ('API response ', '조회 응답 전송'),
                        ('API connected', '연결됨'), ('API disconnected', '연결 종료'),
                        ('API response_failed', '응답 전송 실패'), ('API request_failed', '요청 처리 실패'),
                        ('API processing_failed', '서버 처리 실패'), ('UPLOAD frame', '업로드 수신'),
                        ('UPLOAD authenticated', '인증 성공'), ('UPLOAD ack', '저장 완료 ACK 전송'),
                        ('UPLOAD connected', '연결됨'), ('UPLOAD transport_closed', '통신 종료'),
                        ('Disconnected', '연결 종료'), ('Rejected', '업로드 거부')]
        label = next((text for prefix, text in descriptions if message.startswith(prefix)), '통신 상태')
        return '서버 ' + ('-> ' if outgoing else '<- ') + self.extra['endpoint'] + ' | ' + label + ' | ' + message, kwargs


def control_path(config):
    return Path(config).resolve().parent / 'logs' / (Path(config).name + '.debug.json')


def write_control(path, enabled):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'enabled': enabled}, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_control(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))['enabled']
    if type(value) is not bool:
        raise ValueError('Invalid debug control')
    logger = logging.getLogger('batterywatch')
    level = logging.DEBUG if value else logging.INFO
    if logger.level != level:
        logger.setLevel(level)
        logging.info('통신 디버그 %s (앱/수집기 통신은 계속 동작합니다)', 'ON' if value else 'OFF')


async def watch(path, stop):
    failed = False
    while not stop.is_set():
        try:
            await asyncio.to_thread(apply_control, path)
            failed = False
        except (OSError, ValueError, KeyError, TypeError):
            if not failed:
                logging.warning('디버그 제어 파일을 읽지 못했습니다. 현재 로그 수준을 유지합니다.')
            failed = True
        try:
            await asyncio.wait_for(stop.wait(), 1)
        except asyncio.TimeoutError:
            pass
