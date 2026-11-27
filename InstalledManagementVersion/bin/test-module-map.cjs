const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../public/assets/module-map.js'), 'utf8'), context);
for (const [address, expected] of [
    ['서울특별시 강남구 테헤란로 1', '서울'], [' 대한민국 서울 강남구 ', '서울'],
    ['경기도 광주시 중앙로 1', '경기'], ['광주광역시 북구', '광주'],
    ['전라북도 전주시', '전북'], ['전북특별자치도 전주시', '전북'],
    ['강원특별자치도 원주시', '강원'], ['충남 천안시', '충남'],
    ['', '주소 미분류'], ['미입력', '주소 미분류'], ['광주대로 1', '주소 미분류'],
]) assert.equal(context.moduleMapRegion(address), expected);
const data = context.moduleMapData([
    { address: '서울 강남구', installed: 20, stored: 5 },
    { address: '서울 강남구', installed: '10', stored: '2' },
    { address: '경기도 광주시', installed: 3, stored: 0 },
    { address: '', installed: 4, stored: 1 },
]);
assert.equal(data.get('서울').total, 37);
assert.equal(data.get('서울').addresses.size, 1);
assert.equal(data.get('서울').records, 2);
assert.equal(data.get('경기').total, 3);
assert.equal(data.get('주소 미분류').total, 5);
assert.equal([...data.values()].reduce((sum, group) => sum + group.total, 0), 45);
assert.equal(context.moduleMapData([]).get('서울').total, 0);
console.log('PASS: address aliases, ambiguous city names, installation + storage, duplicate addresses, unknown addresses and empty data');
const sites = context.moduleMapData([
    { address: '서울 강남구', site_name: '강남국소', installed: 10, stored: 44, module_counts: [10], rack_names: ['Rack 01'] },
    { address: '서울 강남구', site_name: '별도국소', installed: 15, stored: 0, module_counts: [10, 5], rack_names: ['주 Rack', '보조 Rack'] },
]);
const items = [...sites.get('서울').addresses.values()];
assert.equal(items.length, 2);
assert.equal(items[0].siteName, '강남국소');
assert.equal(context.moduleMapItemSummary(items[0]), '총 54개 (Rack 01 10대, Rack 외 보관 모듈 수: 44대)');
assert.equal(context.moduleMapItemSummary(items[1]), '총 15개 (주 Rack 10대, 보조 Rack 5대, Rack 외 보관 모듈 수: 0대)');
assert.equal(sites.get('서울').total, 69);
const repeated = context.moduleMapData([
    { address: '', site_name: '', installed: 10, stored: 2, module_counts: [10] },
    { address: '', site_name: '', installed: 5, stored: 3, module_counts: [5] },
]);
const repeatedItem = [...repeated.get('주소 미분류').addresses.values()][0];
assert.equal(repeatedItem.siteName, '국소명 미입력');
assert.equal(context.moduleMapItemSummary(repeatedItem), '총 20개 (Rack 01 15대, Rack 외 보관 모듈 수: 5대)');
console.log('PASS: site separation, rack names, rack totals, stored totals and missing site/name fallbacks');
class Node {
    constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.style = {}; this.attributes = {}; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren() { this.children = []; }
    setAttribute(key, value) { this.attributes[key] = value; }
    addEventListener(name, handler) { this[name] = handler; }
    querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
}
const nodes = new Map();
context.document = {
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node('div')); return nodes.get(id); },
    createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag),
};
const records = [
    { address: '서울 강남구', site_name: '<국소>', work_status: '작업중', installed: 0 },
    { address: '서울 강남구', site_name: '<국소>', work_status: '작업완료', installed: 10 },
    { address: '부산 해운대구', site_name: '부산국소', work_status: '작업완료', installed: 20 },
    { address: '', site_name: '미분류국소', work_status: '작업 중', installed: 0 },
];
const progress = context.moduleMapData(records);
assert.equal(progress.get('서울').inProgress, 1);
assert.equal(progress.get('주소 미분류').inProgress, 1);
assert.equal([...progress.get('서울').addresses.values()][0].statuses.size, 2);
context.renderModuleMap(records);
const buttons = nodes.get('moduleMapCanvas').querySelectorAll('button');
assert.match(buttons.find(button => button.dataset.region === '서울').className, /is-in-progress/);
assert.doesNotMatch(buttons.find(button => button.dataset.region === '부산').className, /is-in-progress/);
assert.match(nodes.get('moduleMapUnknown').className, /is-in-progress/);
buttons.find(button => button.dataset.region === '서울').click();
const heading = nodes.get('moduleMapAddresses').children[0].children[0];
assert.equal(heading.children[0].textContent, '<국소>');
assert.equal(heading.children[1].textContent, '작업중 1건');
assert.equal(heading.children[2].textContent, '작업완료 1건');
context.renderModuleMap(records.map(record => ({ ...record, work_status: '작업완료' })));
assert.ok(nodes.get('moduleMapCanvas').querySelectorAll('button').every(button => !button.className.includes('is-in-progress')));
assert.doesNotMatch(nodes.get('moduleMapUnknown').className, /is-in-progress/);
assert.equal(nodes.get('moduleMapAddresses').children[0].children[0].children[1].textContent, '작업완료');
console.log('PASS: progress regions, zero modules, mixed site statuses, safe text badges and refresh cleanup');
