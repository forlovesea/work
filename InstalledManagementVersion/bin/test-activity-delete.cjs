const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
const fields = new Map();
const calls = [];
const context = vm.createContext({
    document: { querySelector(id) { if (!fields.has(id)) fields.set(id, {}); return fields.get(id); } },
    activityList: { querySelectorAll: () => [] }, activityMessage: {}, refreshActivityButton: {},
    window: { confirm: () => true },
    authenticatedFetch: async (url, options) => { calls.push(JSON.parse(options.body)); return { ok: true, json: async () => ({ deleted_count: 1 }) }; },
    loadActivityLog: async () => {},
});
vm.runInContext('let canDeleteActivity = false; let deletingActivity = false; let activityIds = [1, 2]; const selectedActivityIds = new Set();', context);
const start = source.indexOf('function setActivityPermission(');
vm.runInContext(source.slice(start, source.indexOf('function showLogin(', start)), context);
(async () => {
    await context.deleteActivityLog(true);
    assert.equal(calls.length, 0);
    context.setActivityPermission(true);
    assert.equal(fields.get('#activityDeleteControls').hidden, false);
    assert.equal(fields.get('#deleteSelectedActivity').disabled, true);
    vm.runInContext('selectedActivityIds.add(2)', context);
    context.updateActivityDeleteControls();
    assert.equal(fields.get('#deleteSelectedActivity').disabled, false);
    context.window.confirm = () => false;
    await context.deleteActivityLog(false);
    assert.equal(calls.length, 0);
    context.window.confirm = () => true;
    await context.deleteActivityLog(false);
    assert.equal(calls[0].action, 'delete_activity_selected');
    assert.deepEqual(calls[0].ids, [2]);
    assert.equal(calls[0].confirmed, true);
    await context.deleteActivityLog(true);
    assert.equal(calls[1].action, 'delete_activity_all');
    context.setActivityPermission(false);
    assert.equal(fields.get('#activityDeleteControls').hidden, true);
    assert.equal(fields.get('#deleteAllActivity').disabled, true);
    await context.deleteActivityLog(true);
    assert.equal(calls.length, 2);
    console.log('PASS: activity deletion permissions, selection, confirmation and role reset');
})().catch(error => { console.error(error); process.exitCode = 1; });
