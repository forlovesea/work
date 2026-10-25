const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const fields = new Map();
class Node {
    constructor() { this.children = []; this.style = { setProperty() {} }; }
    append(...children) { this.children.push(...children); }
    replaceChildren() { this.children = []; }
    setAttribute() {}
    addEventListener(name, fn) { this[name] = fn; }
    querySelector(selector) { if (!fields.has(selector)) fields.set(selector, new Node()); return fields.get(selector); }
    showModal() { this.open = true; }
}
const dialog = new Node();
dialog.close = () => { dialog.open = false; };
const pending = [];
const context = vm.createContext({
    URLSearchParams,
    document: { getElementById: () => dialog, createElement: () => new Node(), body: { classList: { add() {}, remove() {} } } },
    authenticatedFetch: (url) => new Promise(resolve => pending.push({ url, resolve })),
});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../public/assets/dashboard.js'), 'utf8'), context);
const reply = (request, records, ok = true) => request.resolve({ ok, json: async () => ({ records, error: ok ? '' : '서버 오류' }) });
(async () => {
    const first = context.openInstallationPopup('SMU02C + Door LCD', '작업완료');
    const query = new URL(pending[0].url, 'https://example.test').searchParams;
    assert.equal(query.get('device'), 'SMU02C + Door LCD');
    assert.equal(query.get('work_status'), '작업완료');
    reply(pending[0], [{ device_name: '<장비>', site_name: '', work_status: '작업완료' }]);
    await first;
    assert.equal(fields.get('tbody').children[0].children.length, 3);
    assert.equal(fields.get('tbody').children[0].children[0].textContent, '<장비>');
    assert.equal(fields.get('tbody').children[0].children[1].textContent, '미입력');
    const stale = context.openInstallationPopup('A', '작업실패');
    const latest = context.openInstallationPopup('B', '방문예정');
    reply(pending[2], []); await latest;
    reply(pending[1], [{ device_name: 'A' }]); await stale;
    assert.equal(fields.get('tbody').children.length, 0);
    assert.match(fields.get('.popup-message').textContent, /없습니다/);
    const closed = context.openInstallationPopup('C', '기타');
    context.closeInstallationPopup();
    reply(pending[3], [{ device_name: 'C' }]); await closed;
    assert.equal(fields.get('tbody').children.length, 0);
    const failed = context.openInstallationPopup('D', '작업보류');
    reply(pending[4], null, false); await failed;
    assert.equal(fields.get('.popup-message').textContent, '서버 오류');
    console.log('PASS: popup filters, three safe text columns, empty/error states and stale/closed response handling');
})().catch(error => { console.error(error); process.exitCode = 1; });
