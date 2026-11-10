"""Application identity and immutable metadata embedded during packaging."""
import json
import sys
from pathlib import Path

VERSION = '3.2.9'
BUILD_DATE = '개발 실행'
if getattr(sys, 'frozen', False):
    metadata = json.loads((Path(sys._MEIPASS) / 'build-info.json').read_text(encoding='utf-8'))
    if metadata['version'] != VERSION:
        raise RuntimeError('Build metadata version mismatch')
    BUILD_DATE = metadata['build_date']


def window_title(description):
    return f'BatteryWatch v{VERSION} | 빌드 {BUILD_DATE} | {description}'
