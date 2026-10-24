const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
const fields = new Map();
const field = id => {
    if (!fields.has(id)) fields.set(id, {});
    return fields.get(id);
};
const context = vm.createContext({
    document: { querySelector: field, createElement: () => ({}) },
    deviceSelect: { value: '', options: [], replaceChildren() { this.options = []; }, append(option) { this.options.push(option); } },
    customDeviceField: {}, customDeviceName: {}, existingVersionInput: {},
    siteNameInput: {}, siteAddressInput: {}, notesInput: {}, workStatusInput: {}, workStatusOtherInput: {},
    updateWorkStatusField() {}, contactList: { replaceChildren() {} }, addContactButton: {}, addContact() {},
});
for (const name of ['versionDisplay', 'fillAdditionalFields', 'renderDevices', 'updateCustomDeviceField', 'applyDeviceVersionDefault']) {
    const start = source.indexOf(`function ${name}(`);
    const next = source.indexOf('\nfunction ', start + 1);
    vm.runInContext(source.slice(start, next), context);
}
context.renderDevices(['Door LCD', 'SMU02C', 'SMU02C + Door LCD']);
assert.equal(context.deviceSelect.options[0].value, 'SMU02C + Door LCD');
assert.equal(context.deviceSelect.options.filter(o => o.value === 'SMU02C + Door LCD').length, 1);
assert.equal(context.deviceSelect.value, 'SMU02C + Door LCD');
assert.equal(context.deviceSelect.options[2].value, 'iIoT Gateway');
context.applyDeviceVersionDefault();
assert.equal(context.existingVersionInput.value, 'V100R024C10SPC235');
assert.equal(field('#doorExistingVersion').required, true);
assert.equal(field('#doorUpgradeVersionField').hidden, false);
assert.equal(field('#existingVersionLabel').textContent, 'SMU02C 기존 설치 버전');
const record = { id: 1, device_name: 'SMU02C + Door LCD', existing_version: '001', upgrade_version: '002', door_existing_version: '008', door_upgrade_version: '009' };
context.fillAdditionalFields(record);
assert.equal(field('#doorExistingVersion').value, '008');
assert.equal(field('#doorUpgradeVersion').value, '009');
assert.equal(context.versionDisplay(record, 'existing_version'), 'SMU02C: 001 / Door LCD: 008');
assert.equal(context.versionDisplay(record, 'upgrade_version'), 'SMU02C: 002 / Door LCD: 009');
context.deviceSelect.value = 'Door LCD';
context.updateCustomDeviceField();
assert.equal(field('#doorExistingVersion').required, false);
assert.equal(field('#doorUpgradeVersion').disabled, true);
assert.equal(field('#doorExistingVersionField').hidden, true);
assert.equal(field('#existingVersionLabel').textContent, '기존 설치 버전');
context.deviceSelect.value = 'SMU02C + Door LCD';
context.updateCustomDeviceField();
assert.equal(field('#doorUpgradeVersion').value, '009');
context.fillAdditionalFields();
assert.equal(field('#doorExistingVersion').value, '');
assert.equal(field('#doorUpgradeVersion').value, '');
for (const [device, expected] of [['SMU02C', 'V100R024C10SPC235'], ['iIoT Gateway', 'V100R024C10SPC265'], ['Door LCD', ''], ['__new__', '']]) {
    context.deviceSelect.value = device;
    context.applyDeviceVersionDefault();
    assert.equal(context.existingVersionInput.value, expected);
}
context.deviceSelect.value = 'iIoT Gateway';
context.existingVersionInput.value = 'user-edited-version';
context.renderDevices(['SMU02C', 'iIoT Gateway', 'Door LCD']);
assert.equal(context.existingVersionInput.value, 'user-edited-version');
assert.equal(context.deviceSelect.options.filter(o => o.value === 'iIoT Gateway').length, 1);
console.log('PASS: device ordering, initial versions, preserved edits, required fields, record loading and display');
