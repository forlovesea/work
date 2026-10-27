const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
class Element {
    constructor() { this.children = []; this.listeners = {}; }
    append(...children) { this.children.push(...children); }
    replaceChildren() { this.children = []; }
    setAttribute() {}
    addEventListener(type, callback) { this.listeners[type] = callback; }
    showModal() { this.open = true; }
    close() { this.open = false; this.listeners.close(); }
}
const elements = new Map();
const context = vm.createContext({ document: {
    querySelector(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
    createElement() { return new Element(); },
} });
vm.runInContext(source.slice(source.indexOf('function locationMatch('), source.indexOf('let isSubmittingRecord')), context);
const match = context.locationMatch;
assert.equal(match('서울 강남-국소', '서울강남국소'), '중복');
assert.equal(match('ＡＢＣ 123', 'abc123'), '중복');
assert.equal(match('', ''), '');
assert.equal(match('---', ' '), '');
assert.equal(match('강남', '강남역'), '');
assert.equal(match('강남국소', '강남국소본관'), '유사');
assert.equal(match('서울강남국소', '서울강남국쏘'), '유사');
assert.equal(match('서울 강남구 테헤란로 123', '서울 강남구 테헤란로 124'), '유사');
assert.equal(match('부산해운대센터', '서울강남국소'), '');
const records = [
    { id: 1, site_name: '강남국소본관', address: '부산', visit_date: '2026-10-01', device_name: 'SMU02C' },
    { id: 2, site_name: '강남국소', address: '서울', visit_date: '2026-10-02', device_name: 'Door LCD' },
    { id: 3, site_name: '다른장소', address: '서울' },
];
const matches = context.findLocationMatches(records, { site_name: '강남국소', address: '서울' });
assert.deepEqual(Array.from(matches, item => item.record.id), [2, 3, 1]);
assert.equal(context.findLocationMatches(records, {}).length, 0);
(async () => {
    let result = context.chooseLocationMatch(matches);
    assert.equal(elements.get('#locationMatchList').children.length, 3);
    elements.get('#locationMatchList').children[0].children[1].listeners.click();
    const edit = await result;
    assert.equal(edit.action, 'edit');
    assert.equal(edit.record, records[1]);
    result = context.chooseLocationMatch(matches);
    elements.get('#ignoreLocationMatches').onclick();
    assert.equal((await result).action, 'create');
    result = context.chooseLocationMatch(matches);
    elements.get('#closeLocationMatches').onclick();
    assert.equal((await result).action, 'cancel');
    result = context.chooseLocationMatch(matches);
    elements.get('#locationMatchDialog').close();
    assert.equal((await result).action, 'cancel');
    console.log('PASS: location matching, ordering, edit target, explicit create and cancellation');
})().catch(error => { console.error(error); process.exitCode = 1; });
