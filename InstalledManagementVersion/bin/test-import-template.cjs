// Run with Node.js; no external packages or live database needed.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
const options = (values) => ({ options: values.map(value => ({ value })) });
const context = vm.createContext({
    deviceSelect: options(['Door LCD', 'SMU02C', '새 장비 & 테스트', '__new__']),
    workStatusInput: options(['방문예정', '작업완료', '작업실패', '작업보류', '기타']),
    document: { querySelector: () => options(['v0.0.0.8']) },
    createZip: files => files,
    downloadBlob: files => { context.files = files; },
    getCellValue: cell => cell.value,
});
for (const name of ['xmlEscape', 'columnName', 'createTemplateCell', 'importTemplateHeaders', 'downloadImportTemplate', 'columnIndexFromReference', 'defaultRackName', 'parseImportRows']) {
    const start = source.indexOf(`function ${name}(`);
    const next = source.indexOf('\nfunction ', start + 1);
    vm.runInContext(source.slice(start, next), context);
}
vm.runInContext('downloadImportTemplate()', context);
const headers = context.importTemplateHeaders();
assert.equal(headers.length, 251);
const sheet = context.files.find(file => file.name === 'xl/worksheets/sheet1.xml').content;
assert.match(sheet, /dataValidations count="105"/);
assert.match(sheet, /sqref="BA2:BA101"/);
assert.match(sheet, /sqref="IQ2:IQ101"/);
assert.match(sheet, /showDropDown="0"/);
assert.match(context.files.find(f => f.name === 'xl/workbook.xml').content, /definedName name="TemplateChoices0"/);
function parse(values, legacy = false) {
    const row = (data, r) => ({ getAttribute: () => String(r), getElementsByTagNameNS: () => data.map((value, c) => ({ value: value || '', getAttribute: () => `${context.columnName(c)}${r}` })) });
    return context.parseImportRows({ getElementsByTagNameNS: () => [row(legacy ? headers.slice(0, 6) : headers, 1), row(values, 2)] }, []);
}
const values = Array(251).fill('');
Object.assign(values, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002', 4: '2', 6: '서울 국소', 7: '주소', 8: '기타', 9: '점검 중', 10: '비고', 11: '홍길동', 12: '01001234567', 51: '주 랙', 52: '4', 54: '10' });
let result = parse(values);
assert.equal(result.errors.length, 0);
assert.equal(result.records[0].contacts[0].phone, '01001234567');
assert.equal(result.records[0].rack_names[1], '랙 02');
assert.equal(result.records[0].module_counts.join(','), '4,10');
assert.equal(parse(['2026-10-22', 'Door LCD', '001', '002', '2', '4,10'], true).errors.length, 0);
for (const changes of [{ 9: '' }, { 12: '' }, { 54: '11' }, { 56: '1' }, { 5: '4,10' }, { 8: '잘못된 상태' }]) {
    assert.ok(parse(Object.assign([...values], changes)).errors.length > 0);
}
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(context.files));
console.log('PASS: template choices, new/legacy imports, contact/rack/status validation');
