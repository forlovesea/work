// Run with Node.js; no external packages or live database needed.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
const options = (values) => ({ options: values.map(value => ({ value })) });
const context = vm.createContext({
    deviceSelect: options(['SMU02C + Door LCD', 'Door LCD', 'SMU02C', '새 장비 & 테스트', '__new__']),
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
assert.equal(headers.length, 23);
assert.equal(headers[21], 'Door LCD 기존 설치 버전');
assert.equal(headers[22], 'Door LCD 업그레이드 버전');
const sheet = context.files.find(file => file.name === 'xl/worksheets/sheet1.xml').content;
assert.match(sheet, /dataValidations count="8"/);
assert.match(sheet, /sqref="Q2:Q101"/);
assert.match(sheet, /sqref="U2:U101"/);
assert.match(sheet, /showDropDown="0"/);
assert.match(context.files.find(f => f.name === 'xl/workbook.xml').content, /definedName name="TemplateChoices0"/);
function parse(values, legacy = false, customHeaders = headers) {
    const row = (data, r) => ({ getAttribute: () => String(r), getElementsByTagNameNS: () => data.map((value, c) => ({ value: value || '', getAttribute: () => `${context.columnName(c)}${r}` })) });
    return context.parseImportRows({ getElementsByTagNameNS: () => [row(legacy ? headers.slice(0, 6) : customHeaders, 1), row(values, 2)] }, []);
}
const values = Array(21).fill('');
Object.assign(values, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002', 4: '2', 6: '서울 국소', 7: '주소', 8: '기타', 9: '점검 중', 10: '비고', 11: '홍길동', 12: '01001234567', 15: '주 Rack', 16: '4', 18: '10' });
let result = parse(values);
assert.equal(result.errors.length, 0);
assert.equal(result.records[0].contacts[0].phone, '01001234567');
assert.equal(result.records[0].rack_names[1], 'Rack 02');
assert.equal(result.records[0].module_counts.join(','), '4,10');
assert.equal(parse(['2026-10-22', 'Door LCD', '001', '002', '2', '4,10'], true).errors.length, 0);
for (const changes of [{ 9: '' }, { 12: '' }, { 18: '11' }, { 20: '1' }, { 5: '4,10' }, { 8: '잘못된 상태' }]) {
    assert.ok(parse(Object.assign([...values], changes)).errors.length > 0);
}
const defaults = Array(21).fill('');
Object.assign(defaults, { 4: '3', 16: '10', 18: '10', 20: '10' });
assert.equal(parse(defaults).records.length, 0);
assert.equal(parse(defaults).errors[0].row, null);
assert.match(parse(defaults).errors[0].message, /등록할 현장 정보가 없습니다/);
Object.assign(defaults, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002' });
assert.equal(parse(defaults).errors.length, 0);
assert.equal(parse(defaults).records[0].module_counts.join(','), '10,10,10');
for (const [cell, value] of [['E2', '3'], ['Q2', '10'], ['S2', '10'], ['U2', '10'], ['U101', '10']]) {
    assert.ok(sheet.includes(`<c r="${cell}" t="inlineStr" s="2"><is><t xml:space="preserve">${value}</t></is></c>`));
}
const oldHeaders = context.importTemplateHeaders(20, 100, false).map(header => header.replaceAll('Rack', '랙'));
const oldValues = Array(251).fill('');
Object.assign(oldValues, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002', 4: '1', 52: '10' });
assert.equal(parse(oldValues, false, oldHeaders).errors.length, 0);
const extendedHeaders = context.importTemplateHeaders(3, 4);
const extendedValues = Array(25).fill('');
Object.assign(extendedValues, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002', 4: '4', 15: '담당자', 16: '01012345678', 18: '10', 20: '10', 22: '10', 24: '5' });
assert.equal(parse(extendedValues, false, extendedHeaders).errors.length, 0);
assert.equal(parse(extendedValues, false, extendedHeaders).records[0].module_counts.join(','), '10,10,10,5');
assert.equal(parse(values, false, context.importTemplateHeaders(2, 3, false)).errors.length, 0);
const combined = Object.assign([...defaults], { 1: 'SMU02C + Door LCD', 21: '0008', 22: '0009' });
const combinedResult = parse(combined);
assert.equal(combinedResult.errors.length, 0);
assert.equal(combinedResult.records[0].existing_version, '001');
assert.equal(combinedResult.records[0].upgrade_version, '002');
assert.equal(combinedResult.records[0].door_existing_version, '0008');
assert.equal(combinedResult.records[0].door_upgrade_version, '0009');
for (const changes of [{ 21: '' }, { 22: '' }, { 22: 'x'.repeat(51) }, { 1: 'Door LCD' }]) {
    assert.ok(parse(Object.assign([...combined], changes)).errors.length > 0);
}
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(context.files));
console.log('PASS: template choices, new/legacy imports, contact/rack/status validation');
