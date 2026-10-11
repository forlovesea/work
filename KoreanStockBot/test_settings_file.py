import json
import tempfile
import unittest
from pathlib import Path
from settings_file import create_template, encrypt_template, load_settings, parse


class SettingsFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/'settings.json'
        self.dest=Path(self.tmp.name)/'settings.ksbkey'
        create_template(self.source)

    def fill(self):
        data=json.loads(self.source.read_text(encoding='utf-8'))
        data['credentials'].update(TOSS_CLIENT_ID=' test-id ',TOSS_CLIENT_SECRET='\tfictional-secret\t',TOSS_ACCOUNT_SEQ=' 123 ')
        self.source.write_text(json.dumps(data),encoding='utf-8')
        return data

    def test_blank_template_has_no_saved_values(self):
        self.assertTrue(all(not v for v in json.loads(self.source.read_text())['credentials'].values()))

    def test_encrypt_roundtrip(self):
        self.fill(); encrypt_template(self.source,self.dest)
        self.assertNotIn(b'fictional-secret',self.dest.read_bytes())
        self.assertEqual(load_settings(self.dest)['credentials']['TOSS_CLIENT_SECRET'],'fictional-secret')
        self.assertTrue(self.source.exists())  # Removal requires the user's UI choice.

    def test_invalid_input_preserves_existing_destination(self):
        self.dest.write_bytes(b'existing')
        with self.assertRaises(ValueError):encrypt_template(self.source,self.dest)
        self.assertEqual(self.dest.read_bytes(),b'existing')

    def test_reject_plaintext_import_and_same_path(self):
        self.fill()
        with self.assertRaises(ValueError):load_settings(self.source)
        with self.assertRaises(ValueError):encrypt_template(self.source,self.source)

    def test_unknown_and_duplicate_fields_rejected(self):
        data=self.fill(); data['credentials']['UNEXPECTED']='x'
        with self.assertRaises(ValueError):parse(json.dumps(data).encode())
        with self.assertRaises(ValueError):parse(b'{"version":1,"version":1}')

    def test_tampering_rejected(self):
        self.fill(); encrypt_template(self.source,self.dest)
        self.dest.write_bytes(self.dest.read_bytes()[:-8])
        with self.assertRaises(Exception):load_settings(self.dest)


if __name__=='__main__':unittest.main()
