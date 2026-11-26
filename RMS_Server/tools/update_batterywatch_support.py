import ast
from pathlib import Path
root=Path(r'C:/Users/Administrator/Downloads/proj/GITHUB/work/BatteryWatch/monitoring-client')
source=next(Path('.').glob('*V3.2.6.py')).read_text(encoding='utf-8')
p=root/'monitor.py'; s=p.read_text(encoding='utf-8')
def method(text,name):
    lines=text.splitlines(keepends=True)
    n=next(n for c in ast.parse(text).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ''.join(lines[n.lineno-1:n.end_lineno])
def replace(old,new):
    global s
    assert old in s, old[:80]
    s=s.replace(old,new,1)
replace('    soc_charge_limit_signal = Signal(bool, object)','    epo_support_signal = Signal(bool)\n    soc_charge_limit_signal = Signal(bool, object)')
replace('        self.initial_ui_emitted = False','        self.epo_support_checked = False\n        self.initial_ui_emitted = False')
replace('    def read_system_name(self, snmp_engine):',method(source,'read_epo_support')+'\n\n    def read_system_name(self, snmp_engine):')
a=source.index('            # 접속 후 첫 정상 수집 시'); b=source.index('            # 기본 모듈 데이터 결과',a)
replace('            # 기본 모듈 데이터 결과',source[a:b]+'            # 기본 모듈 데이터 결과')
replace('        self.is_connected = False','        self.is_connected = False\n        self.epo_supported = False')
replace('            self.is_connected = True','            self.epo_supported = False\n            self.is_connected = True\n            self.update_full_cutoff_button_state()')
replace('            self.snmp_thread.result_signal.connect(self.handle_snmp_result)','            self.snmp_thread.epo_support_signal.connect(self.handle_epo_support_result)\n            self.snmp_thread.result_signal.connect(self.handle_snmp_result)')
replace('                    elif status in (4, 5, 6):','                    elif status in (4, 5, 6) and self.is_epo_supported(module_no):')
replace('    def get_alive_module_numbers(self):',method(source,'is_epo_supported')+'\n\n'+method(source,'handle_epo_support_result')+'\n\n    def get_alive_module_numbers(self):')
for name in ['get_alive_module_numbers','update_full_cutoff_button_state','handle_soc_charge_limit_result']:
    replace(method(s,name),method(source,name))
replace('                if info.get("row_index") is not None\n            )','                if self.is_epo_supported(no)\n            )')
replace('    def execute_cutoff(self, module_no):','    def execute_cutoff(self, module_no):\n        if not self.is_epo_supported(module_no):\n            return False')
replace('            cutoff_btn.setEnabled(True)\n\n        if is_full_cutoff:', '            cutoff_btn.setEnabled(module_no in self.get_alive_module_numbers())\n\n        if is_full_cutoff:')
replace('                    btn.clicked.connect(self.open_soc_charge_limit_dialog)','                    btn.setEnabled(False)\n                    btn.setStyleSheet(self.SOC_CHARGE_DISABLED_STYLE)\n                    btn.clicked.connect(self.open_soc_charge_limit_dialog)')
replace('    def open_soc_charge_limit_dialog(self):','    def open_soc_charge_limit_dialog(self):\n        if not self.is_connected or not getattr(self, "soc_charge_limit_supported", False):\n            return')
replace('    def set_soc_charge_limit(self, enabled, value):','    def set_soc_charge_limit(self, enabled, value):\n        if not self.is_connected or not getattr(self, "soc_charge_limit_supported", False):\n            return False, "SOC support OID not verified"')
ast.parse(s)
p.write_text(s,encoding='utf-8')
p=root/'app_info.py'; p.write_text(p.read_text(encoding='utf-8').replace("VERSION = '3.2.8'","VERSION = '3.2.9'"),encoding='utf-8')
test=Path('tools/test_epo_support.py').read_text(encoding='utf-8').replace('("3.2.6", "3.2.7")','("3.2.9",)').replace('path = next(ROOT.glob(f"*V{version}.py"))','path = ROOT / "monitor.py"')
(root/'tests/test_epo_support.py').write_text(test,encoding='utf-8')
print('Updated BatteryWatch EPO/SOC support and version 3.2.9')
