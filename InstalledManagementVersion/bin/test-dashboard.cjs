const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/dashboard.js'), 'utf8');
const context = vm.createContext({});
vm.runInContext(source, context);
const data = context.installationDashboardData([
    { device_name: 'A', work_status: '작업완료', record_count: '2' },
    { device_name: 'A', work_status: '작업실패', record_count: '1' },
    { device_name: 'B', work_status: '방문예정', record_count: '3' },
    { device_name: 'B', work_status: '작업보류', record_count: '1' },
    { device_name: 'B', work_status: '기타', record_count: '1' },
], ['A', 'B', 'C']);
assert.equal(data.total, 8);
assert.equal(data.complete, 2);
assert.equal(data.incomplete, 6);
assert.equal(data.percent, 25);
assert.equal(data.groups[0].percentages.join(','), '66.7,0,0,33.3,0');
assert.equal(data.groups[1].percentages.join(','), '0,60,20,0,20');
assert.equal(data.groups[2].total, 0);
assert.equal(context.installationDashboardData([]).percent, 0);
assert.equal(context.installationDashboardData([{ device_name: 'A', work_status: '작업완료', record_count: 1 }]).percent, 100);
assert.equal(context.installationDashboardData([{ device_name: 'A', work_status: 'unknown', record_count: 1 }]).incomplete, 1);
const thirds = context.installationDashboardData(['작업완료', '방문예정', '기타'].map(work_status => ({ device_name: 'A', work_status, record_count: 1 })));
assert.equal(Math.round(thirds.groups[0].percentages.reduce((a, b) => a + b, 0) * 10), 1000);
console.log('PASS: weighted completion rate, all work statuses, empty devices, rounding and 0/100% boundaries');
class Node {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.style = { setProperty: (key, value) => { this.style[key] = value; } }; }
    append(...nodes) { this.children.push(...nodes); }
    prepend(node) { this.children.unshift(node); }
    replaceChildren(...nodes) { this.children = nodes; }
    setAttribute(key, value) { this[key] = value; }
}
const nodes = new Map();
context.document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
    createElement(tag) { return new Node(tag); },
};
context.renderInstallationDashboard([
    { device_name: 'A', work_status: '작업완료', record_count: 99 },
    { device_name: 'A', work_status: '작업실패', record_count: 1 },
], ['A', 'B']);
assert.equal(nodes.get('completionPercent').textContent, '99%');
assert.equal(nodes.get('deviceStatusChart').hidden, false);
assert.equal(nodes.get('statusDetails').hidden, false);
assert.equal(nodes.get('statusLegend').children.length, 5);
const columns = nodes.get('deviceStatusChart').children[0].children[1];
assert.equal(columns.children.length, 2);
assert.equal(columns.children[0].children[1].children[2].textContent, '작업실패 1%');
assert.equal(columns.children[1].children[0].children[0].textContent, '기록 없음');
context.renderInstallationDashboard([], ['A']);
assert.equal(nodes.get('completionPercent').textContent, '—');
assert.equal(nodes.get('deviceStatusChart').hidden, true);
assert.equal(nodes.get('statusTable').children.length, 0);
context.renderInstallationDashboard(null);
assert.match(nodes.get('dashboardMessage').textContent, /불러오지 못했습니다/);
assert.equal(nodes.get('statusDetails').hidden, true);
console.log('PASS: chart rendering, small percentage labels, empty state and error cleanup');
