const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const elements = new Map();
const element = id => {
    if (!elements.has(id)) elements.set(id, { value: 'view', handlers: {}, addEventListener(type, handler) { this.handlers[type] = handler; } });
    return elements.get(id);
};
const masked = [{ id: 1, contacts: [{ name: '홍*동', phone: '010-****-5678' }] }];
const raw = [{ id: 1, contacts: [{ name: '홍길동', phone: '010-1234-5678' }] }];
let reply;
let lastPayload;
let exported;
const context = vm.createContext({
    document: { getElementById: id => id === 'contactRevealDialog' ? null : element(id), addEventListener() {} },
    window: { addEventListener() {} }, setTimeout, clearTimeout,
    isLoadingRecords: false, displayedRecords: masked, displayedFilterParams: {},
    exportBaseName: () => 'test',
    authenticatedFetch: async (url, options) => { lastPayload = JSON.parse(options.body); return { ok: reply.ok, json: async () => reply.body }; },
    exportExcel() { exported = context.displayedRecords; },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../public/assets/contact-privacy.js'), 'utf8'), context);
// Inspect the actual Excel sheet XML, including the ordinary export after a one-time grant.
const appSource = fs.readFileSync(path.join(__dirname, '../public/assets/app.js'), 'utf8');
let excelFiles;
const exportContext = vm.createContext({
    displayedRecords: masked, versionDisplay: () => '', moduleSummary: () => '',
    columnName: index => String.fromCharCode(65 + index),
    xmlEscape: value => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;'),
    exportBaseName: () => 'test', createZip: files => files,
    downloadBlob: files => { excelFiles = files; },
});
for (const name of ['exportRows', 'exportExcel']) {
    const start = appSource.indexOf(`function ${name}(`);
    vm.runInContext(appSource.slice(start, appSource.indexOf('\nfunction ', start + 1)), exportContext);
}
exportContext.exportExcel();
let sheet = excelFiles.find(file => file.name === 'xl/worksheets/sheet1.xml').content;
assert.ok(sheet.includes('홍*동 (010-****-5678)'));
assert.ok(!sheet.includes('홍길동') && !sheet.includes('010-1234-5678'));
(async () => {
    context.setContactPrivacy(true);
    element('contactApprovalPurpose').value = 'excel';
    reply = { ok: true, body: { request_id: 'a'.repeat(32), message: 'sent' } };
    await element('requestContactApproval').handlers.click();
    assert.equal(lastPayload.purpose, 'excel');
    assert.deepEqual(lastPayload.ids, [1]);
    assert.equal(element('consumeContactApproval').disabled, false);
    reply = { ok: false, body: { error: 'approval required' } };
    await element('consumeContactApproval').handlers.click();
    assert.equal(exported, undefined);
    assert.equal(context.displayedRecords, masked);
    element('contactApprovalPurpose').value = 'view'; // Original approved purpose remains binding.
    reply = { ok: true, body: { records: raw, purpose: 'excel' } };
    await element('consumeContactApproval').handlers.click();
    assert.equal(lastPayload.purpose, 'excel');
    assert.equal(exported, raw);
    assert.equal(context.displayedRecords, masked);
    assert.equal(element('consumeContactApproval').disabled, true);
    exportContext.displayedRecords = context.displayedRecords;
    exportContext.exportExcel();
    sheet = excelFiles.find(file => file.name === 'xl/worksheets/sheet1.xml').content;
    assert.ok(!sheet.includes('홍길동') && !sheet.includes('010-1234-5678'));
    exported = undefined;
    await element('consumeContactApproval').handlers.click();
    assert.equal(exported, undefined);
    context.setContactPrivacy(false);
    assert.equal(element('contactPrivacyPanel').hidden, true);
    console.log('PASS: approval purpose binding, pending denial, one-time Excel export and masked list restoration');
})().catch(error => { console.error(error); process.exitCode = 1; });
