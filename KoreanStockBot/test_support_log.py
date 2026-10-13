import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from support_log import SupportLog


class SupportLogTests(unittest.TestCase):
    def test_disabled_does_not_create_files_and_toggle_stops_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            log=SupportLog(folder);log.record('START',live=True)
            self.assertEqual(list(Path(folder).iterdir()),[])
            log.enable();log.record('START',live=False);log.disable()
            before=log.path.read_bytes();log.record('STOP')
            self.assertEqual(log.path.read_bytes(),before)
            self.assertIn('로그 생성 꺼짐',before.decode('utf-8-sig'))

    def test_upload_contains_diagnostics_but_no_secrets_or_raw_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);log=SupportLog(root);log.enable()
            log.record('COLLECTION',state='COLLECTION_FAILED',stage='KRX_COMPOSITION_VALIDATE',error_code='LOCAL_FILE_ACCESS',secret='never-share',accountSeq='123456789')
            log.record('COLLECTION',provider='KRX',network=5)
            log.record('CANDIDATE_ERROR',error_code='MISSING_FILE',reason='never-share')
            audit=root/'research/logs/collection.log';audit.parent.mkdir(parents=True)
            audit.write_text('{"event":"FAILED","stage":"NAVER_NEWS_REQUEST","error_code":"HTTP_ERROR","http_status":403,"url":"never-share","time":"2026-10-13T12:00:00+09:00"}\n',encoding='utf-8')
            target=root/'share.zip';log.export(target)
            with ZipFile(target) as archive:
                content='\n'.join(archive.read(name).decode('utf-8-sig') for name in archive.namelist())
                self.assertEqual(len(archive.namelist()),3)
                self.assertIn('자료 수집 실패',content)
                self.assertIn('구성종목 비중 검증',content)
                self.assertIn('403',content)
                self.assertNotIn('never-share',content)
                self.assertNotIn('123456789',content)
                self.assertNotIn('url',content)

    def test_rotation_keeps_bounded_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            log=SupportLog(folder);log.enable()
            for i in range(5):
                log.path.write_text('x'*2_000_001,encoding='utf-8');log.record('START')
            self.assertEqual(len(list((Path(folder)/'logs').iterdir())),4)
