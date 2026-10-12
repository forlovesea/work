import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from collection_log import CollectionLog,CollectionError
from research_sources import Sources,NEWS_URL
from test_etf import NOW


class CollectionLogTests(unittest.TestCase):
    def test_failed_stage_and_unrequested_provider_no_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            log=CollectionLog(Path(folder))
            with self.assertRaises(ValueError):
                with log.stage('KRX_ETF_DAILY','KRX'):raise ValueError('secret-api-key-123')
            self.assertEqual(log.snapshot()['provider_stages']['NAVER'],'NOT_REQUESTED')
            self.assertEqual(log.failed,'KRX_ETF_DAILY')
            log.close()
            text=(Path(folder)/'collection.log').read_text(encoding='utf-8')
            self.assertNotIn('secret-api-key-123',text)
            self.assertEqual([json.loads(x)['event'] for x in text.splitlines()],['START','FAILED'])

    def test_http_auth_error_code_without_url(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Sources(Path(folder)/'cache',NOW);audit=CollectionLog(Path(folder)/'logs');source.audit=audit
            with patch.object(source.opener,'open',side_effect=HTTPError('https://invalid?key=secret',401,'secret',{},None)),patch('research_sources.time.sleep'):
                with self.assertRaises(CollectionError):source.get(NEWS_URL,{'query':'test'})
            audit.close()
            text=(Path(folder)/'logs'/'collection.log').read_text(encoding='utf-8')
            self.assertNotIn('secret',text)
            records=[json.loads(line) for line in text.splitlines()]
            self.assertTrue(any(r.get('http_status')==401 for r in records))
            self.assertEqual(source.health['NAVER']['errors'],1)

    def test_deepest_failure_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            log=CollectionLog(Path(folder))
            with self.assertRaises(CollectionError):
                with log.stage('DART_FINANCIAL_ANALYSIS','DART'):
                    with log.stage('DART_FINANCIAL_REQUEST','DART'):raise CollectionError('DART_API_REJECTED',provider_code='010')
            self.assertEqual(log.failed,'DART_FINANCIAL_REQUEST');log.close()


if __name__=='__main__':unittest.main()
