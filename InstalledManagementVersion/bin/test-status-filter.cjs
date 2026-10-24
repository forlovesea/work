const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
const context = vm.createContext({ URLSearchParams, currentDateMode: () => 'range', filterStartDate: { value: '2026-10-01' }, filterEndDate: { value: '2026-10-31' }, deviceFilter: { value: 'SMU02C' }, versionFilter: { value: 'v1' }, workStatusFilter: { value: '' } });
const start = source.indexOf('function buildQueryString(');
vm.runInContext(source.slice(start, source.indexOf('\nasync function ', start)), context);
for (const status of ['', '방문예정', '작업완료', '작업실패', '작업보류', '기타']) {
    context.workStatusFilter.value = status;
    const query = context.buildQueryString();
    assert.equal(query.get('work_status'), status || null);
    assert.equal(query.get('device'), 'SMU02C');
    assert.equal(query.get('version'), 'v1');
    assert.equal(query.get('start_date'), '2026-10-01');
    assert.equal(query.get('end_date'), '2026-10-31');
    const displayedFilterParams = Object.fromEntries(query.entries());
    assert.equal(displayedFilterParams.work_status, status || undefined);
}
console.log('PASS: work status composes with date/device/version filters and survives filter snapshots');
