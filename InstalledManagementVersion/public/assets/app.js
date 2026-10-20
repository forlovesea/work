const recordForm = document.querySelector('#recordForm');
const visitDateInput = document.querySelector('#visitDate');
const deviceSelect = document.querySelector('#deviceSelect');
const customDeviceField = document.querySelector('#customDeviceField');
const customDeviceName = document.querySelector('#customDeviceName');
const existingVersionInput = document.querySelector('#existingVersion');
const upgradeVersionInput = document.querySelector('#upgradeVersion');
const rackCountInput = document.querySelector('#rackCount');
const rackModules = document.querySelector('#rackModules');
const formMessage = document.querySelector('#formMessage');
const saveButton = document.querySelector('#saveButton');
const previousRecordSelect = document.querySelector('#previousRecordSelect');
const entryTab = document.querySelector('#entryTab');
const queryTab = document.querySelector('#queryTab');
const entryPanel = document.querySelector('#entryPanel');
const queryPanel = document.querySelector('#queryPanel');
const dateModeInputs = [...document.querySelectorAll('input[name="dateMode"]')];
const singleDateFields = document.querySelector('#singleDateFields');
const dateRangeFields = document.querySelector('#dateRangeFields');
const filterDate = document.querySelector('#filterDate');
const filterStartDate = document.querySelector('#filterStartDate');
const filterEndDate = document.querySelector('#filterEndDate');
const deviceFilter = document.querySelector('#deviceFilter');
const versionFilter = document.querySelector('#versionFilter');
const filterMessage = document.querySelector('#filterMessage');
const refreshButton = document.querySelector('#refreshButton');
const historyList = document.querySelector('#historyList');
const recordCount = document.querySelector('#recordCount');
const exportFormat = document.querySelector('#exportFormat');
const reportOption = document.querySelector('#reportOption');
const reportFormat = document.querySelector('#reportFormat');
const exportButton = document.querySelector('#exportButton');
const exportMessage = document.querySelector('#exportMessage');
const printReport = document.querySelector('#printReport');

let savedRecords = [];
let displayedRecords = [];
let filterTimer;
let requestSequence = 0;

function today() {
    const now = new Date();
    const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
    return localDate.toISOString().slice(0, 10);
}

function setFormMessage(message, isError = false) {
    formMessage.textContent = message;
    formMessage.classList.toggle('is-error', isError);
}

function currentModuleCounts() {
    return [...rackModules.querySelectorAll('select')].map((select) => Number(select.value));
}

function renderRackModules(count, selectedCounts = []) {
    rackModules.replaceChildren();

    for (let index = 0; index < count; index += 1) {
        const label = document.createElement('label');
        label.className = 'rack-card';

        const rackName = document.createElement('span');
        rackName.className = 'rack-name';
        rackName.textContent = `랙 ${String(index + 1).padStart(2, '0')}`;

        const select = document.createElement('select');
        select.className = 'module-select';
        select.setAttribute('aria-label', `랙 ${index + 1} 모듈 수`);
        for (let modules = 1; modules <= 10; modules += 1) {
            const option = document.createElement('option');
            option.value = String(modules);
            option.textContent = `${modules}대`;
            select.append(option);
        }
        select.value = String(selectedCounts[index] ?? 1);

        label.append(rackName, select);
        rackModules.append(label);
    }
}

function fillSelect(select, values, emptyLabel, previousValue = select.value) {
    select.replaceChildren();

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = emptyLabel;
    select.append(emptyOption);

    for (const value of values) {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.append(option);
    }

    select.value = values.includes(previousValue) ? previousValue : '';
}

function renderDevices(devices) {
    const selected = deviceSelect.value;
    deviceSelect.replaceChildren();

    for (const name of devices) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        deviceSelect.append(option);
    }

    const newOption = document.createElement('option');
    newOption.value = '__new__';
    newOption.textContent = '+ 새 장치 추가';
    deviceSelect.append(newOption);

    deviceSelect.value = devices.includes(selected) || selected === '__new__'
        ? selected
        : (devices.includes('Door LCD') ? 'Door LCD' : devices[0]);
    updateCustomDeviceField();
}

function updateCustomDeviceField() {
    const isCustom = deviceSelect.value === '__new__';
    customDeviceField.hidden = !isCustom;
    customDeviceName.required = isCustom;
    if (!isCustom) {
        customDeviceName.value = '';
    }
}

function renderInputHistory(records, existingVersions, upgradeVersions) {
    savedRecords = records;
    const selectedId = previousRecordSelect.value;
    previousRecordSelect.replaceChildren();

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '최근 입력한 기록을 선택하면 항목을 자동으로 채웁니다';
    previousRecordSelect.append(placeholder);

    for (const record of records) {
        const option = document.createElement('option');
        option.value = String(record.id);
        option.textContent = `${record.visit_date} · ${record.device_name} · ${record.existing_version} → ${record.upgrade_version}`;
        previousRecordSelect.append(option);
    }
    previousRecordSelect.value = records.some((record) => String(record.id) === selectedId)
        ? selectedId
        : '';

    document.querySelector('#existingVersionOptions').replaceChildren(
        ...existingVersions.map((version) => {
            const option = document.createElement('option');
            option.value = version;
            return option;
        }),
    );
    document.querySelector('#upgradeVersionOptions').replaceChildren(
        ...upgradeVersions.map((version) => {
            const option = document.createElement('option');
            option.value = version;
            return option;
        }),
    );
}

function applyPreviousRecord() {
    const record = savedRecords.find((item) => String(item.id) === previousRecordSelect.value);
    if (!record) {
        return;
    }

    if ([...deviceSelect.options].some((option) => option.value === record.device_name)) {
        deviceSelect.value = record.device_name;
    } else {
        deviceSelect.value = '__new__';
        customDeviceName.value = record.device_name;
    }
    updateCustomDeviceField();
    existingVersionInput.value = record.existing_version;
    upgradeVersionInput.value = record.upgrade_version;
    rackCountInput.value = String(record.rack_count);
    renderRackModules(record.rack_count, record.module_counts);
    visitDateInput.value = today();
    setFormMessage('이전 입력값을 불러왔습니다. 방문 날짜와 내용을 확인해 주세요.');
}

function formatDate(dateString) {
    const [year, month, day] = dateString.split('-');
    return `${year}.${month}.${day}`;
}

function formatExportDate(dateString) {
    return dateString ? formatDate(dateString) : '';
}

function currentFilterSummary() {
    const mode = currentDateMode();
    let dateLabel = '전체 기간';
    if (mode === 'day') {
        dateLabel = formatExportDate(filterDate.value);
    } else if (mode === 'range') {
        dateLabel = `${formatExportDate(filterStartDate.value)} ~ ${formatExportDate(filterEndDate.value)}`;
    }

    return {
        date: dateLabel,
        device: deviceFilter.value || '전체 장비',
        version: versionFilter.value || '전체 버전',
    };
}

function moduleSummary(record) {
    return record.module_counts
        .map((count, index) => `${index + 1}번 랙 ${count}대`)
        .join(', ');
}

function safeFileName(value) {
    return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').replace(/\s+/g, '_');
}

function exportBaseName() {
    const filters = currentFilterSummary();
    const parts = ['설치정보'];
    if (currentDateMode() === 'day' && filterDate.value) {
        parts.push(filterDate.value);
    } else if (currentDateMode() === 'range' && filterStartDate.value && filterEndDate.value) {
        parts.push(`${filterStartDate.value}_${filterEndDate.value}`);
    } else {
        parts.push(today());
    }
    if (deviceFilter.value) {
        parts.push(filters.device);
    }
    if (versionFilter.value) {
        parts.push(filters.version);
    }
    return safeFileName(parts.join('_'));
}

function csvCell(value) {
    let text = String(value ?? '');
    if (/^[\t\r ]*[=+\-@]/.test(text)) {
        text = `'${text}`;
    }
    return `"${text.replace(/"/g, '""')}"`;
}

function exportRows() {
    return [
        ['현장방문날짜', '장비명', '기존 설치 버전', '현재 설치 버전', '축전지 랙 수', '랙별 모듈 수'],
        ...displayedRecords.map((record) => [
            record.visit_date,
            record.device_name,
            record.existing_version,
            record.upgrade_version,
            record.rack_count,
            moduleSummary(record),
        ]),
    ];
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportCsv() {
    const csv = exportRows()
        .map((row) => row.map(csvCell).join(','))
        .join('\r\n');
    downloadBlob(
        new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' }),
        `${exportBaseName()}.csv`,
    );
}

function xmlEscape(value) {
    return String(value ?? '')
        .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}

function columnName(index) {
    let name = '';
    let number = index + 1;
    while (number > 0) {
        const remainder = (number - 1) % 26;
        name = String.fromCharCode(65 + remainder) + name;
        number = Math.floor((number - 1) / 26);
    }
    return name;
}

function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
}

function createZip(files) {
    const encoder = new TextEncoder();
    const localParts = [];
    const centralParts = [];
    let offset = 0;

    for (const file of files) {
        const name = encoder.encode(file.name);
        const data = encoder.encode(file.content);
        const checksum = crc32(data);
        const localHeader = new Uint8Array(30 + name.length);
        const localView = new DataView(localHeader.buffer);
        localView.setUint32(0, 0x04034b50, true);
        localView.setUint16(4, 20, true);
        localView.setUint16(6, 0x0800, true);
        localView.setUint16(8, 0, true);
        localView.setUint32(14, checksum, true);
        localView.setUint32(18, data.length, true);
        localView.setUint32(22, data.length, true);
        localView.setUint16(26, name.length, true);
        localHeader.set(name, 30);
        localParts.push(localHeader, data);

        const centralHeader = new Uint8Array(46 + name.length);
        const centralView = new DataView(centralHeader.buffer);
        centralView.setUint32(0, 0x02014b50, true);
        centralView.setUint16(4, 20, true);
        centralView.setUint16(6, 20, true);
        centralView.setUint16(8, 0x0800, true);
        centralView.setUint16(10, 0, true);
        centralView.setUint32(16, checksum, true);
        centralView.setUint32(20, data.length, true);
        centralView.setUint32(24, data.length, true);
        centralView.setUint16(28, name.length, true);
        centralView.setUint32(42, offset, true);
        centralHeader.set(name, 46);
        centralParts.push(centralHeader);
        offset += localHeader.length + data.length;
    }

    const centralSize = centralParts.reduce((size, part) => size + part.length, 0);
    const end = new Uint8Array(22);
    const endView = new DataView(end.buffer);
    endView.setUint32(0, 0x06054b50, true);
    endView.setUint16(8, files.length, true);
    endView.setUint16(10, files.length, true);
    endView.setUint32(12, centralSize, true);
    endView.setUint32(16, offset, true);

    return new Blob([...localParts, ...centralParts, end], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
}

function exportExcel() {
    const rows = exportRows();
    const sheetRows = rows.map((row, rowIndex) => {
        const cells = row.map((value, columnIndex) => {
            const reference = `${columnName(columnIndex)}${rowIndex + 1}`;
            const style = rowIndex === 0 ? ' s="1"' : '';
            if (rowIndex > 0 && columnIndex === 4) {
                return `<c r="${reference}" t="n"><v>${Number(value)}</v></c>`;
            }
            return `<c r="${reference}" t="inlineStr"${style}><is><t xml:space="preserve">${xmlEscape(value)}</t></is></c>`;
        }).join('');
        return `<row r="${rowIndex + 1}">${cells}</row>`;
    }).join('');
    const files = [
        {
            name: '[Content_Types].xml',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        },
        {
            name: '_rels/.rels',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        },
        {
            name: 'xl/workbook.xml',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000" activeTab="0"/></bookViews><sheets><sheet name="설치 정보" sheetId="1" r:id="rId1"/></sheets></workbook>',
        },
        {
            name: 'xl/_rels/workbook.xml.rels',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        },
        {
            name: 'xl/styles.xml',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="맑은 고딕"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF3157B7"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        },
        {
            name: 'xl/worksheets/sheet1.xml',
            content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="15" customWidth="1"/><col min="2" max="4" width="22" customWidth="1"/><col min="5" max="5" width="14" customWidth="1"/><col min="6" max="6" width="48" customWidth="1"/></cols><sheetData>${sheetRows}</sheetData><autoFilter ref="A1:F${rows.length}"/></worksheet>`,
        },
    ];
    downloadBlob(createZip(files), `${exportBaseName()}.xlsx`);
}

function addReportElement(parent, tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
        element.className = className;
    }
    if (text !== undefined) {
        element.textContent = text;
    }
    parent.append(element);
    return element;
}

function buildPrintableReport(isCustomerReport) {
    const filters = currentFilterSummary();
    const reportDate = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' }).format(new Date());
    const devices = [...new Set(displayedRecords.map((record) => record.device_name))];
    const rackCount = displayedRecords.reduce((sum, record) => sum + record.rack_count, 0);
    const moduleCount = displayedRecords.reduce(
        (sum, record) => sum + record.module_counts.reduce((rackSum, count) => rackSum + count, 0),
        0,
    );

    printReport.replaceChildren();
    printReport.className = `print-report${isCustomerReport ? ' is-customer-report' : ''}`;
    addReportElement(printReport, 'p', 'print-kicker', 'INSTALLED MANAGEMENT VERSION');
    addReportElement(
        printReport,
        'h1',
        'print-title',
        isCustomerReport ? '축전지 시스템 설치 버전 변경 보고서' : '설치 정보 조회 결과',
    );
    addReportElement(
        printReport,
        'p',
        'print-subtitle',
        isCustomerReport
            ? '현장 설치 및 버전 변경 내역을 아래와 같이 보고드립니다.'
            : '설치 정보 조회 화면의 현재 필터 결과',
    );

    const meta = addReportElement(printReport, 'div', 'print-meta');
    for (const [label, value] of [
        ['조회 기간', filters.date],
        ['장비명', filters.device],
        ['현재 설치 버전', filters.version],
        ['작성일', reportDate],
    ]) {
        const item = addReportElement(meta, 'div', 'print-meta-item');
        addReportElement(item, 'span', 'print-meta-label', label);
        addReportElement(item, 'strong', '', value);
    }

    if (isCustomerReport) {
        addReportElement(printReport, 'h2', 'print-section-title', '작업 요약');
        const summary = addReportElement(printReport, 'div', 'print-summary-grid');
        for (const [value, label] of [
            [displayedRecords.length, '조회된 설치 기록'],
            [devices.length, '대상 장비 종류'],
            [rackCount, '대상 랙 합계'],
            [moduleCount, '모듈 합계'],
        ]) {
            const card = addReportElement(summary, 'div', 'print-summary-card');
            addReportElement(card, 'strong', '', String(value));
            addReportElement(card, 'span', '', label);
        }

        const versions = [...new Set(
            displayedRecords.map((record) => `${record.existing_version} → ${record.upgrade_version}`),
        )];
        addReportElement(
            printReport,
            'p',
            'print-overview',
            displayedRecords.length === 0
                ? '선택한 조회 조건에 해당하는 설치 기록이 없습니다.'
                : `조회 조건에 해당하는 ${displayedRecords.length}건의 현장 설치 기록을 정리했습니다. ` +
                  `장비 ${devices.join(', ')}에 대해 확인된 버전 변경 내역은 ${versions.join(' / ')}입니다.`,
        );
        addReportElement(printReport, 'h2', 'print-section-title', '현장별 설치 상세');
    }

    if (displayedRecords.length === 0) {
        addReportElement(printReport, 'p', 'print-no-records', '조회 조건에 해당하는 설치 기록이 없습니다.');
    } else {
        const table = addReportElement(printReport, 'table', 'print-record-table');
        const thead = addReportElement(table, 'thead');
        const header = addReportElement(thead, 'tr');
        for (const heading of ['방문 날짜', '장비명', '기존 버전', '업그레이드 버전', '랙 수', '랙별 모듈 수']) {
            addReportElement(header, 'th', '', heading);
        }
        const tbody = addReportElement(table, 'tbody');
        for (const record of displayedRecords) {
            const row = addReportElement(tbody, 'tr');
            for (const value of [
                record.visit_date,
                record.device_name,
                record.existing_version,
                record.upgrade_version,
                `${record.rack_count}개`,
                moduleSummary(record),
            ]) {
                addReportElement(row, 'td', '', String(value));
            }
        }
    }

    if (isCustomerReport) {
        const notes = addReportElement(printReport, 'section', 'print-notes');
        addReportElement(notes, 'h2', 'print-section-title', '참고 사항');
        addReportElement(
            notes,
            'p',
            '',
            '본 문서는 설치 정보 관리 시스템에 등록된 현장 방문 기록을 기준으로 작성되었습니다. ' +
            '설치 버전 및 랙별 모듈 구성은 현장에서 확인·입력된 기록을 나타냅니다.',
        );
    }

    addReportElement(printReport, 'p', 'print-footer', `Installed Management Version · ${reportDate}`);
}

function showExportMessage(message, isError = false) {
    exportMessage.textContent = message;
    exportMessage.classList.toggle('is-error', isError);
}

function exportResults() {
    if (displayedRecords.length === 0) {
        showExportMessage('내보낼 설치 정보가 없습니다. 조회 조건을 확인해 주세요.', true);
        return;
    }

    if (exportFormat.value === 'csv') {
        exportCsv();
        showExportMessage(`${displayedRecords.length}건의 조회 결과를 CSV 파일로 내보냈습니다.`);
        return;
    }

    if (exportFormat.value === 'excel') {
        exportExcel();
        showExportMessage(`${displayedRecords.length}건의 조회 결과를 Excel 통합 문서로 내보냈습니다.`);
        return;
    }

    exportCsv();
    buildPrintableReport(reportFormat.checked);
    const originalTitle = document.title;
    document.title = `${exportBaseName()}${reportFormat.checked ? '_보고서' : ''}`;
    showExportMessage('CSV 파일을 다운로드했습니다. 인쇄 창에서 PDF로 저장해 주세요.');
    window.addEventListener('afterprint', () => {
        printReport.replaceChildren();
        printReport.className = 'print-report';
        document.title = originalTitle;
    }, { once: true });
    window.print();
}

function createRecordCard(record) {
    const article = document.createElement('article');
    article.className = 'record-card';

    const main = document.createElement('div');
    main.className = 'record-main';
    const titleRow = document.createElement('div');
    titleRow.className = 'record-title-row';
    const title = document.createElement('h3');
    title.textContent = record.device_name;
    const date = document.createElement('time');
    date.dateTime = record.visit_date;
    date.textContent = formatDate(record.visit_date);
    titleRow.append(title, date);

    const versions = document.createElement('p');
    versions.className = 'record-versions';
    versions.append(
        document.createTextNode(record.existing_version),
        document.createTextNode('  →  '),
        document.createTextNode(record.upgrade_version),
    );
    main.append(titleRow, versions);

    const rackSummary = document.createElement('div');
    rackSummary.className = 'record-racks';
    const rackLabel = document.createElement('span');
    rackLabel.className = 'rack-total';
    rackLabel.textContent = `랙 ${record.rack_count}개`;
    const moduleSummary = document.createElement('span');
    moduleSummary.className = 'module-summary';
    moduleSummary.textContent = record.module_counts
        .map((count, index) => `${index + 1}번 ${count}대`)
        .join(' · ');
    rackSummary.append(rackLabel, moduleSummary);
    article.append(main, rackSummary);
    return article;
}

function currentDateMode() {
    return dateModeInputs.find((input) => input.checked)?.value ?? 'all';
}

function updateDateFields() {
    const mode = currentDateMode();
    singleDateFields.hidden = mode !== 'day';
    dateRangeFields.hidden = mode !== 'range';
    filterDate.required = mode === 'day';
    filterStartDate.required = mode === 'range';
    filterEndDate.required = mode === 'range';
}

function buildQueryString() {
    const params = new URLSearchParams();
    const mode = currentDateMode();
    params.set('date_mode', mode);

    if (mode === 'day') {
        params.set('date', filterDate.value);
    } else if (mode === 'range') {
        params.set('start_date', filterStartDate.value);
        params.set('end_date', filterEndDate.value);
    }
    if (deviceFilter.value) {
        params.set('device', deviceFilter.value);
    }
    if (versionFilter.value) {
        params.set('version', versionFilter.value);
    }
    return params;
}

async function loadData() {
    const requestId = ++requestSequence;
    refreshButton.disabled = true;
    exportButton.disabled = true;
    filterMessage.textContent = '';

    try {
        const response = await fetch(`api.php?${buildQueryString().toString()}`, {
            headers: { Accept: 'application/json' },
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || '기록을 불러오지 못했습니다.');
        }
        if (requestId !== requestSequence) {
            return;
        }

        renderDevices(data.devices);
        renderInputHistory(data.input_history, data.existing_versions, data.upgrade_versions);
        fillSelect(deviceFilter, data.devices, '전체 장비');
        fillSelect(versionFilter, data.current_versions, '전체 버전');

        displayedRecords = data.records;
        exportButton.disabled = displayedRecords.length === 0;
        historyList.replaceChildren();
        recordCount.textContent = `총 ${data.records.length}건`;
        if (data.records.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-state';
            empty.textContent = '조건에 맞는 설치 정보가 없습니다.';
            historyList.append(empty);
        } else {
            for (const record of data.records) {
                historyList.append(createRecordCard(record));
            }
        }
    } catch (error) {
        if (requestId !== requestSequence) {
            return;
        }
        recordCount.textContent = '기록을 불러오지 못했습니다.';
        displayedRecords = [];
        exportButton.disabled = true;
        historyList.replaceChildren();
        const errorMessage = document.createElement('p');
        errorMessage.className = 'empty-state is-error';
        errorMessage.textContent = error.message;
        historyList.append(errorMessage);
        filterMessage.textContent = error.message;
    } finally {
        if (requestId === requestSequence) {
            refreshButton.disabled = false;
        }
    }
}

function scheduleFilterLoad() {
    window.clearTimeout(filterTimer);
    filterTimer = window.setTimeout(loadData, 180);
}

function setActiveTab(tab) {
    const showQuery = tab === 'query';
    entryTab.classList.toggle('is-active', !showQuery);
    queryTab.classList.toggle('is-active', showQuery);
    entryTab.setAttribute('aria-selected', String(!showQuery));
    queryTab.setAttribute('aria-selected', String(showQuery));
    entryTab.tabIndex = showQuery ? -1 : 0;
    queryTab.tabIndex = showQuery ? 0 : -1;
    entryPanel.hidden = showQuery;
    queryPanel.hidden = !showQuery;
    if (showQuery) {
        loadData();
    }
}

rackCountInput.addEventListener('input', () => {
    const count = Number(rackCountInput.value);
    if (!Number.isInteger(count) || count < 1 || count > 100) {
        rackModules.replaceChildren();
        return;
    }
    renderRackModules(count, currentModuleCounts());
});

deviceSelect.addEventListener('change', updateCustomDeviceField);
previousRecordSelect.addEventListener('change', applyPreviousRecord);
entryTab.addEventListener('click', () => setActiveTab('entry'));
queryTab.addEventListener('click', () => setActiveTab('query'));
refreshButton.addEventListener('click', loadData);
exportFormat.addEventListener('change', () => {
    reportOption.hidden = exportFormat.value !== 'pdf';
    showExportMessage(exportFormat.value === 'pdf'
        ? 'PDF 저장을 선택하면 CSV 파일도 함께 다운로드됩니다.'
        : '현재 조회된 목록을 선택한 파일 형식으로 내보냅니다.');
});
exportButton.addEventListener('click', exportResults);

for (const input of dateModeInputs) {
    input.addEventListener('change', () => {
        updateDateFields();
        scheduleFilterLoad();
    });
}
for (const input of [filterDate, filterStartDate, filterEndDate, deviceFilter, versionFilter]) {
    input.addEventListener('change', scheduleFilterLoad);
}

recordForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!recordForm.reportValidity()) {
        return;
    }

    const deviceName = deviceSelect.value === '__new__'
        ? customDeviceName.value.trim()
        : deviceSelect.value;
    if (!deviceName) {
        setFormMessage('새 장치명을 입력해 주세요.', true);
        customDeviceName.focus();
        return;
    }

    saveButton.disabled = true;
    setFormMessage('기록을 저장하고 있습니다.');

    try {
        const response = await fetch('api.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
                visit_date: visitDateInput.value,
                device_name: deviceName,
                existing_version: existingVersionInput.value,
                upgrade_version: upgradeVersionInput.value,
                rack_count: Number(rackCountInput.value),
                module_counts: currentModuleCounts(),
            }),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || '기록을 저장하지 못했습니다.');
        }

        recordForm.reset();
        visitDateInput.value = today();
        deviceSelect.value = [...deviceSelect.options].some((option) => option.value === 'Door LCD')
            ? 'Door LCD'
            : deviceSelect.options[0].value;
        rackCountInput.value = '1';
        updateCustomDeviceField();
        renderRackModules(1);
        previousRecordSelect.value = '';
        setFormMessage('방문 기록을 저장했습니다.');
        await loadData();
    } catch (error) {
        setFormMessage(error.message, true);
    } finally {
        saveButton.disabled = false;
    }
});

visitDateInput.value = today();
filterDate.value = today();
filterStartDate.value = today();
filterEndDate.value = today();
updateDateFields();
renderRackModules(1);
loadData();
