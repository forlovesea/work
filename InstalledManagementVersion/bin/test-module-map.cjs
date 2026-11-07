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
