const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
let restored;
let selected;
let focused;
let message;
let card = { getBoundingClientRect: () => ({ top: 900 }), querySelector: () => ({ focus: options => { focused = options; } }) };
const context = vm.createContext({
    historyList: { querySelector: () => card },
    window: { scrollY: 100, scrollTo: options => { restored = options; } },
    setActiveTab: (...args) => { selected = args; },
    requestAnimationFrame: callback => callback(),
    setRecordActionMessage: value => { message = value; },
});
for (const name of ['restoreEditedRecordPosition', 'importNotes']) {
    const start = source.indexOf(`function ${name}(`);
    vm.runInContext(source.slice(start, source.indexOf('\nfunction ', start + 1)), context);
}
context.restoreEditedRecordPosition({ id: 5, scrollY: 800, offset: 120 });
assert.deepEqual(selected, ['query', false]);
assert.equal(restored.top, 880);
assert.equal(focused.preventScroll, true);
card = null;
context.restoreEditedRecordPosition({ id: 5, scrollY: 800, offset: 120 });
assert.equal(restored.top, 800);
assert.match(message, /조회 조건/);
assert.equal(context.importNotes('', ['현장방문날짜: 2026-11-04']), '');
assert.equal(context.importNotes('사용자 메모\n[엑셀 임시값] 현장방문날짜: 2026-11-04\n추가 메모', []), '사용자 메모\n추가 메모');
console.log('PASS: saved edit returns to list position without refetch, missing record fallback and user-only notes');
let editClass;
let entryScroll;
Object.assign(context, {
    entryPanel: { classList: { toggle: (name, enabled) => { editClass = enabled; } }, scrollIntoView: options => { entryScroll = options; } },
    formTitle: {}, saveButton: {}, cancelEditButton: {},
    deviceSelect: { options: [{ value: 'Door LCD' }] },
    visitDateInput: {}, existingVersionInput: {}, upgradeVersionInput: {}, rackCountInput: {}, previousRecordSelect: {},
    updateCustomDeviceField() {}, renderRackModules() {}, fillAdditionalFields() {}, setFormMessage() {},
});
for (const name of ['setEditMode', 'startEditingRecord']) {
    const start = source.indexOf(`function ${name}(`);
    vm.runInContext(source.slice(start, source.indexOf('\nfunction ', start + 1)), context);
}
context.startEditingRecord({ id: 5, device_name: 'Door LCD', visit_date: '2026-11-27', rack_count: 1, module_counts: [10] });
assert.equal(editClass, true);
assert.equal(entryScroll.block, 'start');
assert.equal(context.cancelEditButton.hidden, false);
context.setEditMode();
assert.equal(editClass, false);
assert.equal(context.cancelEditButton.hidden, true);
console.log('PASS: edit scroll targets the form and editing layout resets after exit');
