const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
new vm.Script(source);
const calls = [];
const context = vm.createContext({
    canDeleteRecords: false, displayedRecords: [{ id: 1 }], selectedRecordIds: new Set([1]),
    selectedCount: {}, selectAllRecords: {}, deleteSelectedButton: {}, deleteFilteredButton: {},
    isLoadingRecords: false, isMutatingRecords: false,
    window: { confirm: () => true }, setRecordActionMessage: () => {}, loadData: async () => {},
    authenticatedFetch: async (url, options) => {
        calls.push(JSON.parse(options.body));
        return { ok: true, json: async () => ({ deleted_count: 1 }) };
    },
});
vm.runInContext(source.slice(source.indexOf('function setRecordDeletePermission('), source.indexOf('function setRecordActionMessage(')), context);
vm.runInContext(source.slice(source.indexOf('async function deleteRecords('), source.indexOf('function deleteSelectedRecords(')), context);
(async () => {
    for (const allowed of [false, true, false]) {
        context.selectedRecordIds.add(1);
        context.setRecordDeletePermission(allowed);
        assert.equal(context.deleteSelectedButton.disabled, !allowed);
        assert.equal(context.deleteFilteredButton.disabled, !allowed);
        const before = calls.length;
        await context.deleteRecords({ action: 'delete_selected' }, 'confirm', 'progress');
        await context.deleteRecords({ action: 'delete_filtered' }, 'confirm', 'progress');
        assert.equal(calls.length - before, allowed ? 2 : 0);
    }
    console.log('PASS: record delete buttons, direct handler calls and permission reset');
})().catch(error => { console.error(error); process.exitCode = 1; });
