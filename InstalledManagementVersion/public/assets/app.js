const recordForm = document.querySelector('#recordForm');
const siteNameInput = document.querySelector('#siteName');
const siteAddressInput = document.querySelector('#siteAddress');
const workStatusInput = document.querySelector('#workStatus');
const workStatusOtherInput = document.querySelector('#workStatusOther');
const workStatusOtherField = document.querySelector('#workStatusOtherField');
const notesInput = document.querySelector('#installationNotes');
const contactList = document.querySelector('#contactList');
const addContactButton = document.querySelector('#addContactButton');

function updateWorkStatusField() {
    const isOther = workStatusInput.value === '기타';
    workStatusOtherField.hidden = !isOther;
    workStatusOtherInput.disabled = !isOther;
    workStatusOtherInput.required = isOther;
}

function addContact(contact = {}) {
    if (contactList.children.length >= 20) return;
    const row = document.createElement('div');
    row.className = 'contact-row';
    for (const [key, label, maxLength] of [['name', '이름', 100], ['phone', '연락처', 50]]) {
        const field = document.createElement('label');
        field.className = 'field';
        const caption = document.createElement('span');
        caption.textContent = label;
        const input = document.createElement('input');
        input.type = key === 'phone' ? 'tel' : 'text';
        input.dataset.contactField = key;
        input.maxLength = maxLength;
        input.value = contact[key] || '';
        field.append(caption, input);
        row.append(field);
    }
    const inputs = [...row.querySelectorAll('input')];
    const validatePair = () => {
        const hasValue = inputs.some((input) => input.value.trim());
        inputs.forEach((input) => {
            input.required = hasValue;
            input.setCustomValidity(hasValue && !input.value.trim() ? '담당자 이름과 연락처를 함께 입력해 주세요.' : '');
        });
    };
    inputs.forEach((input) => input.addEventListener('input', validatePair));
    validatePair();
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary-button';
    remove.textContent = '삭제';
    remove.setAttribute('aria-label', '담당자 삭제');
    remove.addEventListener('click', () => {
        row.remove();
        if (!contactList.children.length) addContact();
        addContactButton.disabled = false;
    });
    row.append(remove);
    contactList.append(row);
    addContactButton.disabled = contactList.children.length >= 20;
}

function fillAdditionalFields(record = {}) {
    siteNameInput.value = record.site_name || '';
    siteAddressInput.value = record.address || '';
    notesInput.value = record.notes || '';
    workStatusInput.value = record.work_status || '방문예정';
    workStatusOtherInput.value = record.work_status_other || '';
    updateWorkStatusField();
    contactList.replaceChildren();
    addContactButton.disabled = false;
    const contacts = record.contacts || [];
    (contacts.length ? contacts : [{}]).forEach(addContact);
}

function additionalRecordDetails(record) {
    return [
        ['설치장소(국소)', record.site_name],
        ['주소', record.address],
        ['담당자 정보', (record.contacts || []).map((contact) => `${contact.name} (${contact.phone})`).join(', ')],
        ['작업상태', record.work_status === '기타' ? `기타: ${record.work_status_other || ''}` : record.work_status],
        ['비고', record.notes],
    ].filter(([, value]) => value);
}

workStatusInput.addEventListener('change', updateWorkStatusField);
addContactButton.addEventListener('click', () => {
    addContact();
    contactList.lastElementChild.querySelector('input').focus();
});
const loginPanel = document.querySelector('#loginPanel');
const loginForm = document.querySelector('#loginForm');
const loginPasswordInput = document.querySelector('#loginPassword');
const loginButton = document.querySelector('#loginButton');
const loginMessage = document.querySelector('#loginMessage');
const appShell = document.querySelector('#appShell');
const logoutButton = document.querySelector('#logoutButton');
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
const downloadTemplateButton = document.querySelector('#downloadTemplateButton');
const importFile = document.querySelector('#importFile');
const importPreview = document.querySelector('#importPreview');
const importSummary = document.querySelector('#importSummary');
const importMessage = document.querySelector('#importMessage');
const importErrors = document.querySelector('#importErrors');
const importRows = document.querySelector('#importRows');
const applyImportButton = document.querySelector('#applyImportButton');
const entryTab = document.querySelector('#entryTab');
const queryTab = document.querySelector('#queryTab');
const activityTab = document.querySelector('#activityTab');
const entryPanel = document.querySelector('#entryPanel');
const queryPanel = document.querySelector('#queryPanel');
const activityPanel = document.querySelector('#activityPanel');
const activityCount = document.querySelector('#activityCount');
const refreshActivityButton = document.querySelector('#refreshActivityButton');
const activityMessage = document.querySelector('#activityMessage');
const activityList = document.querySelector('#activityList');
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
const selectAllRecords = document.querySelector('#selectAllRecords');
const selectedCount = document.querySelector('#selectedCount');
const deleteSelectedButton = document.querySelector('#deleteSelectedButton');
const deleteFilteredButton = document.querySelector('#deleteFilteredButton');
const recordActionMessage = document.querySelector('#recordActionMessage');
const cancelEditButton = document.querySelector('#cancelEditButton');
const formTitle = document.querySelector('#form-title');
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
let activityRequestSequence = 0;
let importReadSequence = 0;
let pendingImportRecords = [];
let importValidationErrors = [];
let selectedRecordIds = new Set();
let displayedFilterParams = {};
let isLoadingRecords = false;
let isMutatingRecords = false;
let editingRecordId = null;
let csrfToken = '';

function showLogin(message = '', isError = false) {
    csrfToken = '';
    appShell.hidden = true;
    loginPanel.hidden = false;
    loginMessage.textContent = message;
    loginMessage.classList.toggle('is-error', isError);
    loginPasswordInput.value = '';
    loginPasswordInput.focus();
}

async function authenticatedFetch(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'X-CSRF-Token': csrfToken,
        },
    });
    if (response.status === 401) {
        showLogin('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.', true);
    }
    return response;
}

async function bootstrapSession() {
    try {
        const response = await fetch('api.php?action=session', {
            headers: { Accept: 'application/json' },
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || '로그인 상태를 확인하지 못했습니다.');
        }
        if (!result.authenticated) {
            showLogin();
            return;
        }
        csrfToken = result.csrf_token;
        loginPanel.hidden = true;
        appShell.hidden = false;
        loadData();
    } catch (error) {
        showLogin(error.message, true);
    }
}

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

function defaultRackName(index) {
    return `랙 ${String(index + 1).padStart(2, '0')}`;
}

function currentRackNames() {
    return [...rackModules.querySelectorAll('.rack-name')].map((input, index) =>
        input.value.trim() || defaultRackName(index));
}

function recordRackName(record, index) {
    return record.rack_names?.[index] || defaultRackName(index);
}

function renderRackModules(count, selectedCounts = [], selectedNames = []) {
    rackModules.replaceChildren();

    for (let index = 0; index < count; index += 1) {
        const label = document.createElement('div');
        label.className = 'rack-card';

        const rackName = document.createElement('input');
        rackName.className = 'rack-name';
        rackName.type = 'text';
        rackName.maxLength = 100;
        rackName.value = selectedNames[index] ?? defaultRackName(index);
        rackName.placeholder = defaultRackName(index);
        rackName.setAttribute('aria-label', `${index + 1}번째 랙 이름`);

        const select = document.createElement('select');
        select.className = 'module-select';
        select.setAttribute('aria-label', `랙 ${index + 1} 모듈 수`);
        rackName.addEventListener('input', () => {
            select.setAttribute('aria-label', `${rackName.value.trim() || defaultRackName(index)} 모듈 수`);
        });
        select.setAttribute('aria-label', `${rackName.value.trim() || defaultRackName(index)} 모듈 수`);
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
    renderRackModules(record.rack_count, record.module_counts, record.rack_names);
    fillAdditionalFields(record);
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
        .map((count, index) => `${recordRackName(record, index)} ${count}대`)
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
        ['현장방문날짜', '장비명', '기존 설치 버전', '현재 설치 버전', '축전지 랙 수', '랙별 모듈 수',
            '설치장소(국소)', '주소', '담당자 정보', '작업상태', '비고'],
        ...displayedRecords.map((record) => [
            record.visit_date,
            record.device_name,
            record.existing_version,
            record.upgrade_version,
            record.rack_count,
            moduleSummary(record),
            record.site_name || '',
            record.address || '',
            (record.contacts || []).map((contact) => `${contact.name} (${contact.phone})`).join(', '),
            record.work_status === '기타' ? `기타: ${record.work_status_other || ''}` : record.work_status || '',
            record.notes || '',
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

function createTemplateCell(reference, value, style = '') {
    const styleAttribute = style ? ` s="${style}"` : '';
    if (value === '') {
        return `<c r="${reference}"${styleAttribute}/>`;
    }
    return `<c r="${reference}" t="inlineStr"${styleAttribute}><is><t xml:space="preserve">${xmlEscape(value)}</t></is></c>`;
}

function importTemplateHeaders() {
    return [
        '현장방문날짜',
        '장비명',
        '기존 설치 버전',
        '업그레이드 버전',
        '축전지 랙 수',
        '랙별 모듈 수 (쉼표 구분)',
        '설치장소(국소)', '주소', '작업상태', '기타 작업상태', '비고',
        ...Array.from({ length: 20 }, (_, i) => [`담당자 ${i + 1} 이름`, `담당자 ${i + 1} 연락처`]).flat(),
        ...Array.from({ length: 100 }, (_, i) => [`랙 ${i + 1} 이름`, `랙 ${i + 1} 모듈 수`]).flat(),
    ];
}

function downloadImportTemplate() {
    const headers = importTemplateHeaders();
    const choiceLists = [
        [...deviceSelect.options].map((option) => option.value).filter((value) => value && value !== '__new__'),
        [...document.querySelector('#existingVersionOptions').options].map((option) => option.value),
        [...new Set(['v0.0.0.9', ...[...document.querySelector('#upgradeVersionOptions').options].map((option) => option.value)])],
        [...workStatusInput.options].map((option) => option.value),
    ];
    const validations = [];
    const listValidation = (range, formula, strict = true) => {
        validations.push(`<dataValidation type="list" allowBlank="1" showDropDown="0" showErrorMessage="${strict ? 1 : 0}" errorTitle="선택값 확인" error="목록에서 값을 선택하세요." sqref="${range}"><formula1>${xmlEscape(formula)}</formula1></dataValidation>`);
    };
    choiceLists.forEach((choices, i) => {
        if (choices.length) listValidation(`${['B', 'C', 'D', 'I'][i]}2:${['B', 'C', 'D', 'I'][i]}101`, `TemplateChoices${i}`, i === 3);
    });
    validations.push('<dataValidation type="whole" operator="between" allowBlank="1" showErrorMessage="1" error="1~100 사이 정수를 입력하세요." sqref="E2:E101"><formula1>1</formula1><formula2>100</formula2></dataValidation>');
    for (let i = 0; i < 100; i += 1) {
        const col = columnName(52 + i * 2);
        listValidation(`${col}2:${col}101`, '"1,2,3,4,5,6,7,8,9,10"');
    }
    const dataRows = [
        `<row r="1" ht="30" customHeight="1">${headers.map((value, index) => (
            createTemplateCell(`${columnName(index)}1`, value, '1')
        )).join('')}</row>`,
        ...Array.from({ length: 100 }, (_, rowIndex) => {
            const rowNumber = rowIndex + 2;
            const cells = headers.map((_, columnIndex) => (
                createTemplateCell(`${columnName(columnIndex)}${rowNumber}`, '', '2')
            )).join('');
            return `<row r="${rowNumber}" ht="24" customHeight="1">${cells}</row>`;
        }),
    ].join('');
    const instructionRows = [
        ['작성 안내', '내용'],
        ['입력 방법', '첫 번째 시트 "설치 정보"의 2행부터 현장별로 한 줄씩 입력하세요.'],
        ['현장방문날짜', 'YYYY-MM-DD 형식으로 입력하세요. 예: 2026-10-20'],
        ['장비명', 'Door LCD, SMU02C 또는 등록할 장비명을 입력하세요.'],
        ['버전', '기존 설치 버전과 업그레이드 버전을 빠짐없이 입력하세요.'],
        ['축전지 랙 수', '1~100 사이의 정수로 입력하세요.'],
        ['랙별 모듈 수', '각 랙의 모듈 수 열에서 1~10을 선택하세요. 기존 쉼표 구분 열을 사용해도 됩니다. 두 방식은 함께 입력하지 마세요.'],
        ['설치 정보', '설치장소(국소), 주소, 비고를 입력하세요. 작업상태가 비어 있으면 방문예정으로 등록합니다.'],
        ['작업상태', '목록에서 선택하세요. 기타를 선택하면 기타 작업상태를 반드시 입력하세요.'],
        ['담당자', '최대 20명까지 이름과 연락처를 한 쌍으로 입력하세요. 연락처는 앞자리 0을 유지하는 텍스트 형식입니다.'],
        ['랙 이름', '랙 수만큼 순서대로 입력하세요. 빈 이름은 랙 01 등의 기본 이름을 사용합니다. 최대 100개입니다.'],
        ['선택 항목', '장비명과 버전은 목록에서 선택하거나 새 값을 직접 입력할 수 있습니다.'],
        ['등록 제한', '한 번 업로드할 때 최대 100개 현장을 등록합니다. 빈 행은 무시합니다.'],
        ['주의', '열 제목을 수정하거나 삭제하지 마세요. 업로드 전에 화면에서 모든 행의 검증 결과를 확인합니다.'],
    ];
    const guidanceRows = instructionRows.map((row, rowIndex) => (
        `<row r="${rowIndex + 1}" ht="${rowIndex === 0 ? 28 : 34}" customHeight="1">${
            row.map((value, columnIndex) => createTemplateCell(
                `${columnName(columnIndex)}${rowIndex + 1}`,
                value,
                rowIndex === 0 ? '1' : (columnIndex === 0 ? '3' : '2'),
            )).join('')
        }</row>`
    )).join('');
    const files = [
        {
            name: '[Content_Types].xml',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        },
        {
            name: '_rels/.rels',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        },
        {
            name: 'xl/workbook.xml',
            content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000" activeTab="0"/></bookViews><sheets><sheet name="설치 정보" sheetId="1" r:id="rId1"/><sheet name="작성 안내" sheetId="2" r:id="rId2"/><sheet name="선택 목록" sheetId="3" state="hidden" r:id="rId4"/></sheets><definedNames>${choiceLists.map((choices, i) => choices.length ? `<definedName name="TemplateChoices${i}">'선택 목록'!$${columnName(i)}$1:$${columnName(i)}$${choices.length}</definedName>` : "").join("")}</definedNames></workbook>`,
        },
        {
            name: 'xl/_rels/workbook.xml.rels',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/></Relationships>',
        },
        {
            name: 'xl/styles.xml',
            content: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="@"/></numFmts><fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="맑은 고딕"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF3157B7"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        },
        {
            name: 'xl/worksheets/sheet1.xml',
            content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="18" customWidth="1"/><col min="2" max="4" width="22" customWidth="1"/><col min="5" max="5" width="16" customWidth="1"/><col min="6" max="6" width="34" customWidth="1"/><col min="7" max="251" width="22" customWidth="1"/></cols><sheetData>${dataRows}</sheetData><autoFilter ref="A1:${columnName(headers.length - 1)}101"/><dataValidations count="${validations.length}">${validations.join('')}</dataValidations></worksheet>`,
        },
        {
            name: 'xl/worksheets/sheet2.xml',
            content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols><col min="1" max="1" width="22" customWidth="1"/><col min="2" max="2" width="82" customWidth="1"/></cols><sheetData>${guidanceRows}</sheetData></worksheet>`,
        },
    ];
    files.push({
        name: 'xl/worksheets/sheet3.xml',
        content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${Array.from({ length: Math.max(...choiceLists.map((list) => list.length)) }, (_, r) => `<row r="${r + 1}">${choiceLists.map((list, c) => createTemplateCell(`${columnName(c)}${r + 1}`, list[r] || '')).join('')}</row>`).join('')}</sheetData></worksheet>`,
    });
    downloadBlob(createZip(files), '설치정보_일괄등록_템플릿.xlsx');
}

function parseXml(bytes, label) {
    const xml = new DOMParser().parseFromString(new TextDecoder('utf-8').decode(bytes), 'application/xml');
    if (xml.getElementsByTagName('parsererror').length > 0) {
        throw new Error(`${label} XML을 읽을 수 없습니다.`);
    }
    return xml;
}

function packagePath(basePath, target) {
    const path = target.startsWith('/')
        ? target.slice(1)
        : `${basePath.slice(0, basePath.lastIndexOf('/') + 1)}${target}`;
    const parts = [];
    for (const part of path.split('/')) {
        if (part === '..') {
            parts.pop();
        } else if (part && part !== '.') {
            parts.push(part);
        }
    }
    return parts.join('/');
}

async function inflateRaw(data) {
    let reader;
    try {
        const stream = new Blob([data]).stream()
            .pipeThrough(new DecompressionStream('deflate-raw'));
        reader = stream.getReader();
    } catch {
        throw new Error('Excel 파일 압축을 해제할 수 없습니다. 최신 브라우저에서 다시 시도해 주세요.');
    }

    const chunks = [];
    let size = 0;
    try {
        while (true) {
            const result = await reader.read();
            if (result.done) {
                break;
            }
            size += result.value.length;
            if (size > 20 * 1024 * 1024) {
                await reader.cancel();
                throw new Error('압축 해제 후 파일 크기가 제한(20MB)을 초과합니다.');
            }
            chunks.push(result.value);
        }
    } catch (error) {
        if (error.message === '압축 해제 후 파일 크기가 제한(20MB)을 초과합니다.') {
            throw error;
        }
        throw new Error('Excel 파일 압축을 해제할 수 없습니다. 최신 브라우저에서 다시 시도해 주세요.');
    }

    const output = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
        output.set(chunk, offset);
        offset += chunk.length;
    }
    return output;
}

async function readXlsxEntries(file) {
    if (file.size > 5 * 1024 * 1024) {
        throw new Error('Excel 파일은 5MB 이하만 업로드할 수 있습니다.');
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const minimumEndOffset = Math.max(0, bytes.length - 22 - 65535);
    let endOffset = -1;
    for (let offset = bytes.length - 22; offset >= minimumEndOffset; offset -= 1) {
        if (view.getUint32(offset, true) === 0x06054b50) {
            endOffset = offset;
            break;
        }
    }
    if (endOffset < 0) {
        throw new Error('올바른 XLSX 파일이 아닙니다. Excel 통합 문서(.xlsx)를 선택해 주세요.');
    }

    const diskNumber = view.getUint16(endOffset + 4, true);
    const centralDisk = view.getUint16(endOffset + 6, true);
    const entryCount = view.getUint16(endOffset + 10, true);
    const centralSize = view.getUint32(endOffset + 12, true);
    let offset = view.getUint32(endOffset + 16, true);
    if (diskNumber !== 0 || centralDisk !== 0 || entryCount > 1000 ||
        offset + centralSize > endOffset) {
        throw new Error('분할되었거나 지원하지 않는 XLSX 파일입니다.');
    }

    const entries = new Map();
    let totalUncompressedSize = 0;
    for (let index = 0; index < entryCount; index += 1) {
        const entryOffset = offset;
        if (offset + 46 > bytes.length || view.getUint32(offset, true) !== 0x02014b50) {
            throw new Error('Excel 파일의 ZIP 구성이 올바르지 않습니다.');
        }
        const flags = view.getUint16(offset + 8, true);
        const method = view.getUint16(offset + 10, true);
        const compressedSize = view.getUint32(offset + 20, true);
        const uncompressedSize = view.getUint32(offset + 24, true);
        const nameLength = view.getUint16(offset + 28, true);
        const extraLength = view.getUint16(offset + 30, true);
        const commentLength = view.getUint16(offset + 32, true);
        const localOffset = view.getUint32(offset + 42, true);
        const name = new TextDecoder('utf-8').decode(bytes.subarray(offset + 46, offset + 46 + nameLength));
        offset += 46 + nameLength + extraLength + commentLength;

        if ((flags & 1) !== 0 || (method !== 0 && method !== 8) ||
            compressedSize === 0xffffffff || uncompressedSize === 0xffffffff ||
            localOffset + 30 > bytes.length) {
            throw new Error('암호화되었거나 지원하지 않는 압축 형식의 Excel 파일입니다.');
        }
        totalUncompressedSize += uncompressedSize;
        if (totalUncompressedSize > 20 * 1024 * 1024) {
            throw new Error('압축 해제 후 파일 크기가 제한(20MB)을 초과합니다.');
        }
        if (view.getUint32(localOffset, true) !== 0x04034b50) {
            throw new Error('Excel 파일의 ZIP 항목이 손상되었습니다.');
        }
        const localNameLength = view.getUint16(localOffset + 26, true);
        const localExtraLength = view.getUint16(localOffset + 28, true);
        const dataOffset = localOffset + 30 + localNameLength + localExtraLength;
        if (dataOffset + compressedSize > bytes.length) {
            throw new Error('Excel 파일의 ZIP 데이터가 손상되었습니다.');
        }
        const compressedData = bytes.subarray(dataOffset, dataOffset + compressedSize);
        let content;
        if (method === 0) {
            content = compressedData;
        } else {
            if (typeof DecompressionStream !== 'function') {
                throw new Error('이 브라우저는 XLSX 압축 해제를 지원하지 않습니다. 최신 Chrome, Edge 또는 Safari를 사용해 주세요.');
            }
            content = await inflateRaw(compressedData);
        }
        if (content.length !== uncompressedSize || crc32(content) !== view.getUint32(entryOffset + 16, true)) {
            throw new Error('Excel 파일이 손상되었거나 올바르지 않습니다.');
        }
        if (entries.has(name)) {
            throw new Error('Excel 파일에 중복된 ZIP 항목이 있습니다.');
        }
        entries.set(name, content);
    }
    return entries;
}

function parseSharedStrings(xml) {
    return [...xml.getElementsByTagNameNS('*', 'si')].map((item) => (
        [...item.getElementsByTagNameNS('*', 't')].map((text) => text.textContent || '').join('')
    ));
}

function getCellValue(cell, sharedStrings) {
    const type = cell.getAttribute('t');
    if (type === 'inlineStr') {
        return [...cell.getElementsByTagNameNS('*', 't')]
            .map((text) => text.textContent || '')
            .join('');
    }
    const valueNode = cell.getElementsByTagNameNS('*', 'v')[0];
    const value = valueNode?.textContent ?? '';
    if (type === 's') {
        const index = Number(value);
        if (!Number.isInteger(index) || index < 0 || index >= sharedStrings.length) {
            throw new Error('Excel 공유 문자열 인덱스가 올바르지 않습니다.');
        }
        return sharedStrings[index];
    }
    return value;
}

function columnIndexFromReference(reference) {
    const letters = reference.match(/^[A-Z]+/i)?.[0];
    if (!letters) {
        return -1;
    }
    let index = 0;
    for (const letter of letters.toUpperCase()) {
        index = index * 26 + letter.charCodeAt(0) - 64;
    }
    return index - 1;
}

function parseImportRows(sheetXml, sharedStrings) {
    const rows = [...sheetXml.getElementsByTagNameNS('*', 'row')];
    if (rows.length === 0 || Number(rows[0].getAttribute('r') || 1) !== 1) {
        throw new Error('첫 번째 행에는 템플릿의 열 제목이 있어야 합니다.');
    }
    const headerValues = [];
    for (const cell of rows[0].getElementsByTagNameNS('*', 'c')) {
        const column = columnIndexFromReference(cell.getAttribute('r') || '');
        if (column >= 0) {
            headerValues[column] = getCellValue(cell, sharedStrings).trim();
        }
    }
    const legacy = headerValues.filter(Boolean).length === 6;
    const expectedHeaders = legacy ? importTemplateHeaders().slice(0, 6) : importTemplateHeaders();
    const missingHeaders = expectedHeaders.filter((header) => !headerValues.includes(header));
    if (missingHeaders.length > 0 || expectedHeaders.some((header, index) => headerValues[index] !== header)) {
        throw new Error('열 제목이 템플릿과 다릅니다. 열 제목을 바꾸지 말고 새 템플릿을 내려받아 주세요.');
    }

    const records = [];
    const errors = [];
    for (const [rowIndex, row] of rows.slice(1).entries()) {
        const rowNumber = Number(row.getAttribute('r')) || rowIndex + 2;
        const values = [];
        for (const cell of row.getElementsByTagNameNS('*', 'c')) {
            const column = columnIndexFromReference(cell.getAttribute('r') || '');
            if (column >= expectedHeaders.length) {
                if (getCellValue(cell, sharedStrings).trim() !== '') {
                    errors.push({ row: rowNumber, message: '템플릿에 없는 열에 값이 있습니다.' });
                }
            } else if (column >= 0) {
                values[column] = getCellValue(cell, sharedStrings).trim();
            }
        }
        if (!values.some((value) => value)) {
            continue;
        }
        if (records.length >= 100) {
            errors.push({ row: rowNumber, message: '한 번에 최대 100개 현장까지만 등록할 수 있습니다.' });
            continue;
        }

        let [visitDate, deviceName, existingVersion, upgradeVersion, rackCountText, moduleCountsText] = values;
        const rackCount = /^\d+$/.test(rackCountText || '') ? Number(rackCountText) : NaN;
        const extra = { site_name: values[6] || '', address: values[7] || '', work_status: values[8] || '방문예정', work_status_other: values[9] || '', notes: values[10] || '', contacts: [] };
        const fail = (message) => errors.push({ row: rowNumber, message });
        for (const [key, label, limit] of [['site_name', '설치장소', 100], ['address', '주소', 300], ['work_status_other', '기타 작업상태', 100], ['notes', '비고', 2000]]) {
            if ([...extra[key]].length > limit) fail(`${label}은(는) ${limit}자 이내로 입력하세요.`);
        }
        if (!['방문예정', '작업완료', '작업실패', '작업보류', '기타'].includes(extra.work_status)) fail('작업상태를 목록에서 선택하세요.');
        if (extra.work_status === '기타' && !extra.work_status_other) fail('기타 작업상태를 입력하세요.');
        if (extra.work_status !== '기타') extra.work_status_other = '';
        for (let i = 0; i < 20; i += 1) {
            const name = values[11 + i * 2] || '';
            const phone = values[12 + i * 2] || '';
            if (!name && !phone) continue;
            if (!name || !phone || [...name].length > 100 || [...phone].length > 50) fail(`담당자 ${i + 1}: 이름(100자 이내)과 연락처(50자 이내)를 함께 입력하세요.`);
            extra.contacts.push({ name, phone });
        }
        if (!legacy) {
            extra.rack_names = [];
            const selectedModules = [];
            for (let i = 0; i < 100; i += 1) {
                const name = values[51 + i * 2] || '';
                const count = values[52 + i * 2] || '';
                if (i < rackCount) {
                    extra.rack_names.push(name || defaultRackName(i));
                    selectedModules.push(count);
                    if ([...name].length > 100) fail(`랙 ${i + 1} 이름은 100자 이내로 입력하세요.`);
                } else if (name || count) fail(`랙 ${i + 1}: 입력한 랙 수를 초과한 값이 있습니다.`);
            }
            if (selectedModules.some(Boolean)) {
                if (moduleCountsText) fail('쉼표 구분 모듈 수와 개별 랙 모듈 수 중 한 방식만 입력하세요.');
                moduleCountsText = selectedModules.join(',');
            }
        }
        const moduleCounts = (moduleCountsText || '').split(',').map((value) => (
            /^\d+$/.test(value.trim()) ? Number(value.trim()) : NaN
        ));
        const parsedDate = /^\d{4}-\d{2}-\d{2}$/.test(visitDate || '')
            ? new Date(`${visitDate}T00:00:00Z`)
            : null;
        if (!parsedDate || Number.isNaN(parsedDate.getTime()) ||
            parsedDate.toISOString().slice(0, 10) !== visitDate) {
            errors.push({ row: rowNumber, message: '현장방문날짜는 실제 날짜인 YYYY-MM-DD 형식이어야 합니다.' });
        }
        for (const [value, label, maxLength] of [
            [deviceName, '장비명', 100],
            [existingVersion, '기존 설치 버전', 50],
            [upgradeVersion, '업그레이드 버전', 50],
        ]) {
            if (!value || [...value].length > maxLength) {
                errors.push({ row: rowNumber, message: `${label}을(를) 입력하고 ${maxLength}자 이내로 작성하세요.` });
            }
        }
        if (!Number.isInteger(rackCount) || rackCount < 1 || rackCount > 100) {
            errors.push({ row: rowNumber, message: '축전지 랙 수는 1~100 사이의 정수여야 합니다.' });
        }
        if (!moduleCountsText || !moduleCounts.every((count) => Number.isInteger(count) && count >= 1 && count <= 10)) {
            errors.push({ row: rowNumber, message: '랙별 모듈 수는 쉼표로 구분한 1~10 사이의 정수여야 합니다.' });
        } else if (moduleCounts.length !== rackCount) {
            errors.push({ row: rowNumber, message: '랙 수와 쉼표로 구분한 모듈 수의 개수가 일치해야 합니다.' });
        }
        records.push({
            visit_date: visitDate || '',
            device_name: deviceName || '',
            existing_version: existingVersion || '',
            upgrade_version: upgradeVersion || '',
            rack_count: rackCount,
            module_counts: moduleCounts,
            ...extra,
            source_row: rowNumber,
        });
    }

    if (records.length === 0 && errors.length === 0) {
        errors.push({ row: null, message: '등록할 현장 정보가 없습니다. 두 번째 행부터 값을 입력하세요.' });
    }
    return { records, errors };
}

async function readImportWorkbook(file) {
    const entries = await readXlsxEntries(file);
    const workbookBytes = entries.get('xl/workbook.xml');
    const relationshipsBytes = entries.get('xl/_rels/workbook.xml.rels');
    if (!workbookBytes || !relationshipsBytes) {
        throw new Error('Excel 통합 문서 구조가 올바르지 않습니다.');
    }
    const workbook = parseXml(workbookBytes, '통합 문서');
    const relationships = parseXml(relationshipsBytes, '통합 문서 관계');
    const sheet = [...workbook.getElementsByTagNameNS('*', 'sheet')]
        .find((item) => item.getAttribute('name') === '설치 정보');
    if (!sheet) {
        throw new Error('"설치 정보" 시트를 찾을 수 없습니다. 제공된 템플릿을 사용해 주세요.');
    }
    const relationshipId = sheet.getAttributeNS(
        'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'id',
    );
    const relation = [...relationships.getElementsByTagNameNS('*', 'Relationship')]
        .find((item) => item.getAttribute('Id') === relationshipId);
    if (!relation) {
        throw new Error('설치 정보 시트 연결을 찾을 수 없습니다.');
    }
    const sheetPath = packagePath('xl/workbook.xml', relation.getAttribute('Target'));
    const sheetBytes = entries.get(sheetPath);
    if (!sheetBytes) {
        throw new Error('설치 정보 시트 데이터를 찾을 수 없습니다.');
    }
    const sharedStringsBytes = entries.get('xl/sharedStrings.xml');
    const sharedStrings = sharedStringsBytes
        ? parseSharedStrings(parseXml(sharedStringsBytes, '공유 문자열'))
        : [];
    return parseImportRows(parseXml(sheetBytes, '설치 정보 시트'), sharedStrings);
}

function renderImportPreview(records, errors) {
    pendingImportRecords = records;
    importValidationErrors = errors;
    importPreview.hidden = false;
    importSummary.textContent = `${records.length}개 현장 · ${errors.length}개 오류`;
    importMessage.textContent = errors.length > 0
        ? '오류가 하나라도 있으면 등록할 수 없습니다. Excel의 해당 행을 수정한 뒤 다시 업로드하세요.'
        : '아래 내용을 확인하세요. 등록을 누르면 모든 현장이 한 번에 저장됩니다.';
    importMessage.classList.toggle('is-error', errors.length > 0);
    applyImportButton.disabled = records.length === 0 || errors.length > 0;
    importErrors.replaceChildren();
    for (const error of errors) {
        const item = document.createElement('li');
        item.textContent = `${error.row ? `${error.row}행: ` : ''}${error.message}`;
        importErrors.append(item);
    }
    importRows.replaceChildren();
    for (const record of records) {
        const row = document.createElement('article');
        row.className = 'import-row';
        const heading = document.createElement('strong');
        heading.textContent = `${record.source_row}행 · ${record.visit_date} · ${record.device_name}`;
        const detail = document.createElement('span');
        detail.textContent = `${record.existing_version} → ${record.upgrade_version} · 랙 ${record.rack_count}개 · 모듈 ${moduleSummary(record)}`;
        row.append(heading, detail);
        importRows.append(row);
    }
}

async function handleImportFileChange() {
    const requestId = ++importReadSequence;
    const file = importFile.files?.[0];
    pendingImportRecords = [];
    importValidationErrors = [];
    importPreview.hidden = !file;
    if (!file) {
        return;
    }

    applyImportButton.disabled = true;
    importSummary.textContent = 'Excel 파일을 확인하고 있습니다.';
    importMessage.textContent = '';
    importErrors.replaceChildren();
    importRows.replaceChildren();
    try {
        const result = await readImportWorkbook(file);
        if (requestId !== importReadSequence) {
            return;
        }
        renderImportPreview(result.records, result.errors);
    } catch (error) {
        if (requestId !== importReadSequence) {
            return;
        }
        renderImportPreview([], [{ row: null, message: error.message }]);
    }
}

async function applyImport() {
    if (pendingImportRecords.length === 0 || importValidationErrors.length > 0) {
        return;
    }
    applyImportButton.disabled = true;
    importMessage.classList.remove('is-error');
    importMessage.textContent = '일괄 등록 중입니다. 창을 닫지 마세요.';
    try {
        const response = await authenticatedFetch('api.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
                action: 'bulk_create',
                records: pendingImportRecords,
            }),
        });
        const result = await response.json();
        if (!response.ok) {
            if (Array.isArray(result.row_errors)) {
                const errors = result.row_errors.flatMap((rowError) => (
                    rowError.messages.map((message) => ({
                        row: rowError.row,
                        message,
                    }))
                ));
                renderImportPreview(pendingImportRecords, errors);
            }
            throw new Error(result.error || '일괄 등록을 완료하지 못했습니다.');
        }

        importFile.value = '';
        importPreview.hidden = true;
        importRows.replaceChildren();
        pendingImportRecords = [];
        importValidationErrors = [];
        setFormMessage(`${result.created_count}개 현장 기록을 모두 등록했습니다.`);
        await loadData();
    } catch (error) {
        importMessage.textContent = error.message;
        importMessage.classList.add('is-error');
        applyImportButton.disabled = pendingImportRecords.length === 0 || importValidationErrors.length > 0;
    }
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
            content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="15" customWidth="1"/><col min="2" max="4" width="22" customWidth="1"/><col min="5" max="5" width="14" customWidth="1"/><col min="6" max="6" width="48" customWidth="1"/></cols><sheetData>${sheetRows}</sheetData><autoFilter ref="A1:K${rows.length}"/></worksheet>`,
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
            const details = additionalRecordDetails(record);
            if (details.length) {
                const detailRow = addReportElement(tbody, 'tr');
                const detailCell = addReportElement(detailRow, 'td', 'record-site-detail',
                    details.map(([label, value]) => `${label}: ${value}`).join('\n'));
                detailCell.colSpan = 6;
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
    article.dataset.recordId = String(record.id);

    const main = document.createElement('div');
    main.className = 'record-main';
    const titleRow = document.createElement('div');
    titleRow.className = 'record-title-row';
    const selection = document.createElement('input');
    selection.className = 'record-selection';
    selection.type = 'checkbox';
    selection.setAttribute('aria-label', `${record.visit_date} ${record.device_name} 기록 선택`);
    selection.checked = selectedRecordIds.has(record.id);
    const title = document.createElement('h3');
    title.textContent = record.device_name;
    const date = document.createElement('time');
    date.dateTime = record.visit_date;
    date.textContent = formatDate(record.visit_date);
    titleRow.append(selection, title, date);

    const versions = document.createElement('p');
    versions.className = 'record-versions';
    versions.append(
        document.createTextNode(record.existing_version),
        document.createTextNode('  →  '),
        document.createTextNode(record.upgrade_version),
    );
    main.append(titleRow, versions);
    for (const [label, value] of additionalRecordDetails(record)) {
        const detail = document.createElement('p');
        detail.className = 'record-site-detail';
        detail.textContent = `${label}: ${value}`;
        main.append(detail);
    }

    const rackSummary = document.createElement('div');
    rackSummary.className = 'record-racks';
    const rackLabel = document.createElement('span');
    rackLabel.className = 'rack-total';
    rackLabel.textContent = `랙 ${record.rack_count}개`;
    const moduleSummary = document.createElement('span');
    moduleSummary.className = 'module-summary';
    moduleSummary.textContent = record.module_counts
        .map((count, index) => `${recordRackName(record, index)} ${count}대`)
        .join(' · ');
    const editButton = document.createElement('button');
    editButton.className = 'record-edit-button';
    editButton.type = 'button';
    editButton.dataset.action = 'edit';
    editButton.textContent = '수정';
    editButton.setAttribute('aria-label', `${record.visit_date} ${record.device_name} 설치 기록 수정`);
    rackSummary.append(rackLabel, moduleSummary, editButton);
    article.append(main, rackSummary);
    return article;
}

function updateRecordActionControls() {
    const visibleIds = displayedRecords.map((record) => record.id);
    const selectedVisibleCount = visibleIds.filter((id) => selectedRecordIds.has(id)).length;
    selectedCount.textContent = `(${selectedVisibleCount})`;
    selectAllRecords.checked = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length;
    selectAllRecords.indeterminate = selectedVisibleCount > 0 && selectedVisibleCount < visibleIds.length;
    selectAllRecords.disabled = isLoadingRecords || isMutatingRecords || visibleIds.length === 0;
    deleteSelectedButton.disabled = isLoadingRecords || isMutatingRecords || selectedVisibleCount === 0;
    deleteFilteredButton.disabled = isLoadingRecords || isMutatingRecords || visibleIds.length === 0;
}

function setRecordActionMessage(message, isError = false) {
    recordActionMessage.textContent = message;
    recordActionMessage.classList.toggle('is-error', isError);
}

function setEditMode(recordId = null) {
    editingRecordId = recordId;
    const isEditing = recordId !== null;
    formTitle.textContent = isEditing ? '설치 정보 수정' : '설치 정보 입력';
    saveButton.textContent = isEditing ? '수정 내용 저장' : '＋ 방문 기록 저장';
    cancelEditButton.hidden = !isEditing;
}

function startEditingRecord(record) {
    if (![...deviceSelect.options].some((option) => option.value === record.device_name)) {
        const option = document.createElement('option');
        option.value = record.device_name;
        option.textContent = record.device_name;
        deviceSelect.insertBefore(option, deviceSelect.lastElementChild);
    }
    deviceSelect.value = record.device_name;
    updateCustomDeviceField();
    visitDateInput.value = record.visit_date;
    existingVersionInput.value = record.existing_version;
    upgradeVersionInput.value = record.upgrade_version;
    rackCountInput.value = String(record.rack_count);
    renderRackModules(record.rack_count, record.module_counts, record.rack_names);
    previousRecordSelect.value = '';
    setEditMode(record.id);
    fillAdditionalFields(record);
    setFormMessage(`${record.visit_date} ${record.device_name} 기록을 수정 중입니다.`);
    setActiveTab('entry');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetEntryForm() {
    recordForm.reset();
    fillAdditionalFields();
    visitDateInput.value = today();
    deviceSelect.value = [...deviceSelect.options].some((option) => option.value === 'Door LCD')
        ? 'Door LCD'
        : deviceSelect.options[0].value;
    rackCountInput.value = '1';
    updateCustomDeviceField();
    renderRackModules(1);
    previousRecordSelect.value = '';
    setEditMode();
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
    const queryParams = buildQueryString();
    isLoadingRecords = true;
    updateRecordActionControls();
    refreshButton.disabled = true;
    exportButton.disabled = true;
    filterMessage.textContent = '';

    try {
        const response = await authenticatedFetch(`api.php?${queryParams.toString()}`, {
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
        displayedFilterParams = Object.fromEntries(queryParams.entries());
        const visibleIds = new Set(displayedRecords.map((record) => record.id));
        selectedRecordIds = new Set([...selectedRecordIds].filter((id) => visibleIds.has(id)));
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
        updateRecordActionControls();
    } catch (error) {
        if (requestId !== requestSequence) {
            return;
        }
        recordCount.textContent = '기록을 불러오지 못했습니다.';
        displayedRecords = [];
        selectedRecordIds.clear();
        exportButton.disabled = true;
        historyList.replaceChildren();
        const errorMessage = document.createElement('p');
        errorMessage.className = 'empty-state is-error';
        errorMessage.textContent = error.message;
        historyList.append(errorMessage);
        filterMessage.textContent = error.message;
        updateRecordActionControls();
    } finally {
        if (requestId === requestSequence) {
            refreshButton.disabled = false;
            isLoadingRecords = false;
            updateRecordActionControls();
        }
    }
}

function scheduleFilterLoad() {
    window.clearTimeout(filterTimer);
    filterTimer = window.setTimeout(loadData, 180);
}

function formatActivityTime(value) {
    const timestamp = new Date(`${value.replace(' ', 'T')}Z`);
    if (Number.isNaN(timestamp.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat('ko-KR', {
        dateStyle: 'medium',
        timeStyle: 'medium',
        timeZone: 'Asia/Seoul',
    }).format(timestamp);
}

function createActivityCard(activity) {
    const labels = {
        create: '등록',
        update: '수정',
        delete: '삭제',
    };
    const article = document.createElement('article');
    article.className = 'activity-item';

    const time = document.createElement('time');
    time.className = 'activity-time';
    time.dateTime = `${activity.occurred_at.replace(' ', 'T')}Z`;
    time.textContent = formatActivityTime(activity.occurred_at);

    const content = document.createElement('div');
    content.className = 'activity-content';
    const titleRow = document.createElement('div');
    titleRow.className = 'activity-title-row';
    const badge = document.createElement('span');
    badge.className = `activity-badge is-${activity.action}`;
    badge.textContent = labels[activity.action] ?? '작업';
    const summary = document.createElement('strong');
    summary.className = 'activity-summary';
    summary.textContent = activity.summary;
    titleRow.append(badge, summary);
    content.append(titleRow);

    const details = activity.details ?? {};
    const detailLines = [];
    if (activity.action === 'update' && details.changes) {
        for (const [field, change] of Object.entries(details.changes)) {
            detailLines.push(`${field}: ${change.before} → ${change.after}`);
        }
    } else if (details.record) {
        const record = details.record;
        detailLines.push(`랙 ${record.rack_count}개 · 모듈 ${moduleSummary(record)}`);
    }
    if (detailLines.length > 0) {
        const detailList = document.createElement('div');
        detailList.className = 'activity-details';
        for (const line of detailLines) {
            const detail = document.createElement('p');
            detail.className = 'activity-detail-line';
            detail.textContent = line;
            detailList.append(detail);
        }
        content.append(detailList);
    }
    article.append(time, content);
    return article;
}

async function loadActivityLog() {
    const requestId = ++activityRequestSequence;
    refreshActivityButton.disabled = true;
    activityMessage.textContent = '';
    try {
        const response = await authenticatedFetch('api.php?action=activity', {
            headers: { Accept: 'application/json' },
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || '작업 이력을 불러오지 못했습니다.');
        }
        if (requestId !== activityRequestSequence) {
            return;
        }
        const activities = data.activities;
        if (!Array.isArray(activities)) {
            throw new Error('작업 이력 응답 형식이 올바르지 않습니다.');
        }
        activityCount.textContent = `최근 1년 · 총 ${activities.length}건`;
        activityList.replaceChildren();
        if (activities.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-state';
            empty.textContent = '최근 1년간 등록·수정·삭제된 작업이 없습니다.';
            activityList.append(empty);
        } else {
            for (const activity of activities) {
                activityList.append(createActivityCard(activity));
            }
        }
    } catch (error) {
        if (requestId !== activityRequestSequence) {
            return;
        }
        activityCount.textContent = '작업 이력을 불러오지 못했습니다.';
        activityList.replaceChildren();
        const errorMessage = document.createElement('p');
        errorMessage.className = 'empty-state is-error';
        errorMessage.textContent = error.message;
        activityList.append(errorMessage);
        activityMessage.textContent = error.message;
    } finally {
        if (requestId === activityRequestSequence) {
            refreshActivityButton.disabled = false;
        }
    }
}

function setActiveTab(tab) {
    const showQuery = tab === 'query';
    const showActivity = tab === 'activity';
    entryTab.classList.toggle('is-active', !showQuery && !showActivity);
    queryTab.classList.toggle('is-active', showQuery);
    activityTab.classList.toggle('is-active', showActivity);
    entryTab.setAttribute('aria-selected', String(!showQuery && !showActivity));
    queryTab.setAttribute('aria-selected', String(showQuery));
    activityTab.setAttribute('aria-selected', String(showActivity));
    entryTab.tabIndex = showQuery || showActivity ? -1 : 0;
    queryTab.tabIndex = showQuery ? 0 : -1;
    activityTab.tabIndex = showActivity ? 0 : -1;
    entryPanel.hidden = showQuery || showActivity;
    queryPanel.hidden = !showQuery;
    activityPanel.hidden = !showActivity;
    if (showQuery) {
        loadData();
    } else if (showActivity) {
        loadActivityLog();
    }
}

async function deleteRecords(payload, confirmation, progressMessage) {
    if (!window.confirm(confirmation)) {
        return;
    }
    isMutatingRecords = true;
    updateRecordActionControls();
    setRecordActionMessage(progressMessage);
    try {
        const response = await authenticatedFetch('api.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || '설치 기록을 삭제하지 못했습니다.');
        }
        selectedRecordIds.clear();
        setRecordActionMessage(`${result.deleted_count}건의 설치 기록을 삭제했습니다.`);
        await loadData();
    } catch (error) {
        setRecordActionMessage(error.message, true);
    } finally {
        isMutatingRecords = false;
        updateRecordActionControls();
    }
}

function deleteSelectedRecords() {
    const recordIds = displayedRecords
        .filter((record) => selectedRecordIds.has(record.id))
        .map((record) => record.id);
    if (recordIds.length === 0) {
        setRecordActionMessage('삭제할 기록을 먼저 선택해 주세요.', true);
        return;
    }
    void deleteRecords(
        { action: 'delete_selected', record_ids: recordIds },
        `선택한 ${recordIds.length}건의 설치 기록을 삭제할까요? 삭제한 기록은 복구할 수 없습니다.`,
        `${recordIds.length}건의 선택 기록을 삭제하고 있습니다.`,
    );
}

function deleteFilteredRecords() {
    const count = displayedRecords.length;
    if (count === 0) {
        return;
    }
    void deleteRecords(
        { action: 'delete_filtered', filters: displayedFilterParams },
        `현재 조회 결과 ${count}건을 모두 삭제할까요?\n다른 조회 조건의 기록은 삭제되지 않습니다. 삭제한 기록은 복구할 수 없습니다.`,
        `현재 조회 조건에 맞는 ${count}건을 삭제하고 있습니다.`,
    );
}

rackCountInput.addEventListener('input', () => {
    const count = Number(rackCountInput.value);
    if (!Number.isInteger(count) || count < 1 || count > 100) {
        return;
    }
    renderRackModules(count, currentModuleCounts(), currentRackNames());
});

loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!loginForm.reportValidity()) {
        return;
    }
    loginButton.disabled = true;
    loginMessage.classList.remove('is-error');
    loginMessage.textContent = '로그인 중입니다.';
    try {
        const response = await fetch('api.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
                action: 'login',
                password: loginPasswordInput.value,
            }),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || '로그인하지 못했습니다.');
        }
        csrfToken = result.csrf_token;
        loginPasswordInput.value = '';
        loginMessage.textContent = '';
        loginPanel.hidden = true;
        appShell.hidden = false;
        loadData();
    } catch (error) {
        loginMessage.textContent = error.message;
        loginMessage.classList.add('is-error');
        loginPasswordInput.select();
    } finally {
        loginButton.disabled = false;
    }
});

logoutButton.addEventListener('click', async () => {
    logoutButton.disabled = true;
    try {
        const response = await authenticatedFetch('api.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({ action: 'logout' }),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || '로그아웃하지 못했습니다.');
        }
        showLogin('로그아웃했습니다.');
    } catch (error) {
        if (loginPanel.hidden) {
            window.alert(error.message);
        } else {
            loginMessage.textContent = error.message;
            loginMessage.classList.add('is-error');
        }
    } finally {
        logoutButton.disabled = false;
    }
});

deviceSelect.addEventListener('change', updateCustomDeviceField);
previousRecordSelect.addEventListener('change', applyPreviousRecord);
downloadTemplateButton.addEventListener('click', downloadImportTemplate);
importFile.addEventListener('change', handleImportFileChange);
applyImportButton.addEventListener('click', applyImport);
entryTab.addEventListener('click', () => setActiveTab('entry'));
queryTab.addEventListener('click', () => setActiveTab('query'));
activityTab.addEventListener('click', () => setActiveTab('activity'));
refreshButton.addEventListener('click', loadData);
refreshActivityButton.addEventListener('click', loadActivityLog);
selectAllRecords.addEventListener('change', () => {
    for (const record of displayedRecords) {
        if (selectAllRecords.checked) {
            selectedRecordIds.add(record.id);
        } else {
            selectedRecordIds.delete(record.id);
        }
    }
    for (const checkbox of historyList.querySelectorAll('.record-selection')) {
        checkbox.checked = selectAllRecords.checked;
    }
    updateRecordActionControls();
});
deleteSelectedButton.addEventListener('click', deleteSelectedRecords);
deleteFilteredButton.addEventListener('click', deleteFilteredRecords);
historyList.addEventListener('change', (event) => {
    if (!(event.target instanceof HTMLInputElement) || !event.target.matches('.record-selection')) {
        return;
    }
    const recordId = Number(event.target.closest('.record-card')?.dataset.recordId);
    if (!Number.isInteger(recordId)) {
        return;
    }
    if (event.target.checked) {
        selectedRecordIds.add(recordId);
    } else {
        selectedRecordIds.delete(recordId);
    }
    updateRecordActionControls();
});
historyList.addEventListener('click', (event) => {
    if (!(event.target instanceof Element) || !event.target.matches('[data-action="edit"]')) {
        return;
    }
    const recordId = Number(event.target.closest('.record-card')?.dataset.recordId);
    const record = displayedRecords.find((item) => item.id === recordId);
    if (record) {
        startEditingRecord(record);
    }
});
exportFormat.addEventListener('change', () => {
    reportOption.hidden = exportFormat.value !== 'pdf';
    showExportMessage(exportFormat.value === 'pdf'
        ? 'PDF 저장을 선택하면 CSV 파일도 함께 다운로드됩니다.'
        : '현재 조회된 목록을 선택한 파일 형식으로 내보냅니다.');
});
exportButton.addEventListener('click', exportResults);
cancelEditButton.addEventListener('click', () => {
    resetEntryForm();
    setFormMessage('설치 정보 수정을 취소했습니다.');
});

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

    const isEditing = editingRecordId !== null;
    saveButton.disabled = true;
    setFormMessage(isEditing ? '수정 내용을 저장하고 있습니다.' : '기록을 저장하고 있습니다.');

    try {
        const payload = {
            visit_date: visitDateInput.value,
            device_name: deviceName,
            existing_version: existingVersionInput.value,
            upgrade_version: upgradeVersionInput.value,
            rack_count: Number(rackCountInput.value),
            module_counts: currentModuleCounts(),
            rack_names: currentRackNames(),
            site_name: siteNameInput.value.trim(),
            address: siteAddressInput.value.trim(),
            contacts: [...contactList.children].map((row) => ({
                name: row.querySelector('[data-contact-field="name"]').value.trim(),
                phone: row.querySelector('[data-contact-field="phone"]').value.trim(),
            })).filter((contact) => contact.name || contact.phone),
            notes: notesInput.value.trim(),
            work_status: workStatusInput.value,
            work_status_other: workStatusInput.value === '기타' ? workStatusOtherInput.value.trim() : '',
        };
        if (isEditing) {
            payload.action = 'update_record';
            payload.id = editingRecordId;
        }
        const response = await authenticatedFetch('api.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || (isEditing
                ? '수정 내용을 저장하지 못했습니다.'
                : '기록을 저장하지 못했습니다.'));
        }

        resetEntryForm();
        setFormMessage(isEditing ? '설치 기록을 수정했습니다.' : '방문 기록을 저장했습니다.');
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
fillAdditionalFields();
bootstrapSession();
