// Run with Node.js; no external packages or live database needed.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/assets/app.js'), 'utf8');
const options = (values) => ({ options: values.map(value => ({ value })) });
const context = vm.createContext({
    deviceSelect: options(['SMU02C + Door LCD', 'Door LCD', 'iIoT Gateway', 'SMU02C', '새 장비 & 테스트', '__new__']),
    workStatusInput: options(['방문예정', '작업완료', '작업실패', '작업보류', '기타']),
    document: { querySelector: () => options(['v0.0.0.8']) },
    createZip: files => files,
    downloadBlob: files => { context.files = files; },
    getCellValue: cell => cell.value,
});
for (const name of ['xmlEscape', 'columnName', 'createTemplateCell', 'importTemplateHeaders', 'legacyImportTemplateHeaders', 'basicImportHeaders', 'downloadImportTemplate', 'columnIndexFromReference', 'defaultRackName', 'parseBasicImportRows', 'parseImportRows']) {
    const start = source.indexOf(`function ${name}(`);
    const next = source.indexOf('\nfunction ', start + 1);
    vm.runInContext(source.slice(start, next), context);
}
vm.runInContext('downloadImportTemplate(true)', context);
const headers = context.legacyImportTemplateHeaders();
assert.equal(headers.length, 23);
assert.equal(headers[21], 'Door LCD 기존 설치 버전');
assert.equal(headers[22], 'Door LCD 업그레이드 버전');
const sheet = context.files.find(file => file.name === 'xl/worksheets/sheet1.xml').content;
assert.match(sheet, /dataValidations count="6"/);
assert.match(sheet, /sqref="O2:O101"/);
assert.match(sheet, /showDropDown="0"/);
assert.match(context.files.find(f => f.name === 'xl/workbook.xml').content, /definedName name="TemplateChoices0"/);
function parse(values, legacy = false, customHeaders = headers, formulas = {}) {
    const row = (data, r) => ({ getAttribute: () => String(r), getElementsByTagNameNS: () => data.map((value, c) => ({ value: value || '', getAttribute: () => `${context.columnName(c)}${r}`, getElementsByTagNameNS: () => r === 2 && formulas[c] ? [{ textContent: formulas[c] }] : [] })) });
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
for (const [cell, value] of [['M2', '1'], ['O2', '10'], ['O101', '10']]) {
    assert.ok(sheet.includes(`<c r="${cell}" t="inlineStr" s="2"><is><t xml:space="preserve">${value}</t></is></c>`));
}
const oldHeaders = context.legacyImportTemplateHeaders(20, 100, false).map(header => header.replaceAll('Rack', '랙'));
const oldValues = Array(251).fill('');
Object.assign(oldValues, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002', 4: '1', 52: '10' });
assert.equal(parse(oldValues, false, oldHeaders).errors.length, 0);
const extendedHeaders = context.legacyImportTemplateHeaders(3, 4);
const extendedValues = Array(25).fill('');
Object.assign(extendedValues, { 0: '2026-10-22', 1: 'Door LCD', 2: '001', 3: '002', 4: '4', 15: '담당자', 16: '01012345678', 18: '10', 20: '10', 22: '10', 24: '5' });
assert.equal(parse(extendedValues, false, extendedHeaders).errors.length, 0);
assert.equal(parse(extendedValues, false, extendedHeaders).records[0].module_counts.join(','), '10,10,10,5');
assert.equal(parse(values, false, context.legacyImportTemplateHeaders(2, 3, false)).errors.length, 0);
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
const screenHeaders = context.importTemplateHeaders(2, 3, true);
assert.equal(screenHeaders.join('|'), '설치장소(국소)|주소|작업상태|기타 작업상태|담당자 1 이름|담당자 1 연락처|담당자 2 이름|담당자 2 연락처|현장방문날짜|장비명|새 장치명|기존 설치 버전|업그레이드 버전|Door LCD 기존 설치 버전|Door LCD 업그레이드 버전|Rack 수|Rack 1 이름|Rack 1 모듈 수|Rack 2 이름|Rack 2 모듈 수|Rack 3 이름|Rack 3 모듈 수|비고');
const toScreen = (row, targetHeaders = screenHeaders, sourceHeaders = headers) => targetHeaders.map(header => row[sourceHeaders.indexOf(header === 'Rack 수' ? '축전지 Rack 수' : header)] || '');
const screenRow = toScreen(combined);
Object.assign(screenRow, { 0: '국소', 1: '주소', 2: '기타', 3: '점검 중', 4: '담당자1', 5: '01001234567', 6: '담당자2', 7: '01011112222', 22: '비고' });
const parsedScreen = parse(screenRow, false, screenHeaders);
assert.equal(parsedScreen.errors.length, 0);
assert.equal(parsedScreen.records[0].site_name, '국소');
assert.equal(parsedScreen.records[0].contacts[1].phone, '01011112222');
assert.equal(parsedScreen.records[0].door_upgrade_version, '0009');
assert.equal(parsedScreen.records[0].notes, '비고');
assert.equal(parsedScreen.records[0].module_counts.join(','), '10,10,10');
const custom = toScreen(defaults);
Object.assign(custom, { 9: '+ 새 장치 추가', 10: 'Custom Device' });
assert.equal(parse(custom, false, screenHeaders).records[0].device_name, 'Custom Device');
assert.equal(parse(custom, false, screenHeaders).errors.length, 0);
assert.ok(parse(Object.assign([...custom], { 10: '' }), false, screenHeaders).errors.length);
assert.ok(parse(Object.assign([...custom], { 9: 'Door LCD' }), false, screenHeaders).errors.length);
const blankScreen = Array(23).fill('');
Object.assign(blankScreen, { 15: '3', 17: '10', 19: '10', 21: '10' });
assert.equal(parse(blankScreen, false, screenHeaders).records.length, 0);
const extendedScreenHeaders = context.importTemplateHeaders(3, 4, true);
assert.equal(parse(toScreen(extendedValues, extendedScreenHeaders, extendedHeaders), false, extendedScreenHeaders).errors.length, 0);
assert.match(sheet, /sqref="G2:G101"/);
assert.match(sheet, /sqref="C2:C101"/);
assert.match(sheet, /sqref="M2:M101"/);
const compactHeaders = context.importTemplateHeaders();
assert.equal(compactHeaders.length, 16);
assert.equal(compactHeaders.includes('기타 작업상태'), false);
assert.equal(compactHeaders.includes('담당자 2 이름'), false);
assert.equal(compactHeaders.includes('Rack 2 이름'), false);
const compactValues = compactHeaders.map(header => ({ '작업상태': '기타', '현장방문날짜': '2026-10-24', '장비명': 'SMU02C', '기존 설치 버전': 'V100R024C10SPC235', '업그레이드 버전': 'new-version', 'Rack 수': '1', 'Rack 1 모듈 수': '10' }[header] || ''));
assert.equal(parse(compactValues, false, compactHeaders).errors.length, 0);
assert.equal(parse(compactValues, false, compactHeaders).records[0].rack_count, 1);
assert.equal(parse(compactValues, false, compactHeaders).records[0].work_status_other, '');
const compactBlank = compactHeaders.map(header => header === 'Rack 수' ? '1' : header === 'Rack 1 모듈 수' ? '10' : '');
assert.equal(parse(compactBlank, false, compactHeaders).records.length, 0);
assert.match(sheet, /<c r="I2" t="str"><f>IF\(OR\(G2=/);
assert.match(sheet, /V100R024C10SPC235/);
assert.match(sheet, /V100R024C10SPC265/);
assert.match(sheet, /conditionalFormatting sqref="K2:L101"/);
assert.match(context.files.find(file => file.name === 'xl/workbook.xml').content, /fullCalcOnLoad="1"/);
assert.match(sheet, /<c r="J2" s="2"\/>/);
assert.match(sheet, /<c r="L2" s="2"\/>/);
const defaultFormula = 'IF(OR(G2="SMU02C + Door LCD",G2="SMU02C"),"V100R024C10SPC235",IF(G2="iIoT Gateway","V100R024C10SPC265",""))';
for (const [device, expected] of [['SMU02C', 'V100R024C10SPC235'], ['iIoT Gateway', 'V100R024C10SPC265']]) {
    const row = Object.assign([...compactValues], { 6: device, 8: '' });
    const result = parse(row, false, compactHeaders, { 8: defaultFormula });
    assert.equal(result.errors.length, 0);
    assert.equal(result.records[0].existing_version, expected);
    assert.ok(parse(row, false, compactHeaders).errors.length > 0);
    const override = parse(Object.assign([...row], { 8: 'manual-version' }), false, compactHeaders);
    assert.equal(override.records[0].existing_version, 'manual-version');
}
vm.runInContext('downloadImportTemplate()', context);
const basicHeaders = context.basicImportHeaders();
assert.equal(basicHeaders.join(','), '설치장소(국소),주소,작업상태,담당자 이름,담당자 연락처,현장방문날짜,장비명');
const basicSheet = context.files.find(file => file.name === 'xl/worksheets/sheet1.xml').content;
assert.match(basicSheet, /autoFilter ref="A1:G101"/);
assert.match(basicSheet, /dataValidations count="2"/);
assert.doesNotMatch(basicSheet, /<f>|conditionalFormatting|기존 설치 버전|Rack 수/);
for (const device of ['SMU02C + Door LCD', 'Door LCD', 'iIoT Gateway', 'SMU02C', '새 장비']) {
    const row = ['국소', '주소', '방문예정', '담당자', '01001234567', '2026-10-25', device];
    const result = parse(row, false, basicHeaders);
    assert.equal(result.errors.length, 0);
    assert.equal(result.records[0].contacts[0].phone, '01001234567');
    assert.equal(result.records[0].upgrade_version, '');
    assert.equal(result.records[0].rack_count, 1);
    assert.equal(result.records[0].import_layout, 'basic');
    assert.equal(result.records[0].device_name, device);
}
const base = ['국소', '주소', '기타', '담당자', '01001234567', '2026-10-25', 'Door LCD'];
for (const changes of [{ 4: '' }, { 5: '2026-02-30' }, { 6: '' }, { 2: '알수없음' }, { 7: '추가값' }]) {
    assert.ok(parse(Object.assign([...base], changes), false, basicHeaders).errors.length);
}
assert.equal(parse(Array(7).fill(''), false, basicHeaders).records.length, 0);
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(context.files));
console.log('PASS: template choices, new/legacy imports, contact/rack/status validation');
