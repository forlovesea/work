"""Offline regression tests using real pysnmp values and Qt buttons."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QPushButton
from pysnmp.proto.rfc1902 import Integer32, ObjectName, OctetString
from pysnmp.proto.rfc1905 import noSuchInstance, noSuchObject, endOfMibView

ROOT = Path(__file__).resolve().parents[1]
OID = "1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1"
APP = QApplication.instance() or QApplication([])


class EpoSupportTests(unittest.TestCase):
    def test_both_versions(self):
        for version in ("3.2.9",):
            with self.subTest(version=version):
                self.check_version(version)

    def check_version(self, version):
        path = ROOT / "monitor.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {"read_epo_support", "is_epo_supported", "get_alive_module_numbers",
                 "update_full_cutoff_button_state", "handle_epo_support_result",
                 "execute_cutoff"}
        methods = [n for c in tree.body if isinstance(c, ast.ClassDef)
                   for n in c.body if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = {"Integer32": Integer32,
                 "EpoCutoffThread": SimpleNamespace(EPO_PREPARE_OID=OID)}
        for name in ("CommunityData", "UdpTransportTarget", "ContextData",
                     "ObjectType", "ObjectIdentity"):
            scope[name] = Mock()
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), "exec"), scope)
        worker = SimpleNamespace(ip="test", port=161, community="test", running=True,
                                 SNMP_TIMEOUT_SEC=1, SNMP_RETRIES=0,
                                 tx_signal=Mock(), rx_signal=Mock())
        ui_type = type("TestUi", (), {n: scope[n] for n in names})
        ui = ui_type()
        ui.is_connected = True
        ui.epo_supported = False
        ui.snmp_thread = worker
        ui.sender = lambda: worker
        ui.module_map = {1: {"row_index": "100"}, 2: {"row_index": "101"}}
        ui.module_data = {"100": {"status": 4}, "101": {"status": 6}}
        ui.cutoff_buttons = {n: QPushButton() for n in (1, 2)}
        ui.full_cutoff_button = QPushButton()
        ui.full_restore_button = QPushButton()
        ui.handle_soc_charge_limit_result = Mock()
        buttons = [*ui.cutoff_buttons.values(), ui.full_cutoff_button, ui.full_restore_button]
        ui.update_full_cutoff_button_state()
        self.assertTrue(all(not b.isEnabled() for b in buttons))

        for value in (noSuchInstance, noSuchObject, endOfMibView,
                      OctetString("1"), Integer32(2147483647), Integer32(1)):
            scope["bulkCmd"] = Mock(return_value=iter([
                (None, 0, 0, [(ObjectName(OID), Integer32(1))])]))
            scope["getCmd"] = Mock(return_value=iter([
                (None, 0, 0, [(ObjectName(OID), value)])]))
            supported = scope["read_epo_support"](worker, None)
            expected = value is not noSuchInstance and type(value) is Integer32 and int(value) == 1
            self.assertEqual(supported, expected)
            ui.handle_epo_support_result(supported)
            self.assertTrue(all(b.isEnabled() == expected for b in buttons))
            if not expected:
                self.assertFalse(ui.execute_cutoff(1))

        # Captured table skips .11.1 and advances to .12.1.
        scope["bulkCmd"] = Mock(return_value=iter([(None, 0, 0, [
            (ObjectName(OID.replace(".11.1", ".12.1")), Integer32(2))])]))
        self.assertFalse(scope["read_epo_support"](worker, None))
        ui.is_connected = False
        ui.update_full_cutoff_button_state()
        ui.is_connected = True
        ui.update_full_cutoff_button_state()
        self.assertTrue(all(not b.isEnabled() for b in buttons))
        ui.sender = lambda: SimpleNamespace(running=True)
        ui.handle_epo_support_result(True)
        self.assertFalse(ui.epo_supported)


if __name__ == "__main__":
    unittest.main()
