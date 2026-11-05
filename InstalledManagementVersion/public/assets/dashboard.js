const installationStatuses = [
    { name: '작업완료', color: '#a8dfcc', ink: '#205c4a' },
    { name: '방문예정', color: '#b8cef3', ink: '#2e4d7a' },
    { name: '작업보류', color: '#f4dba5', ink: '#71551e' },
    { name: '작업실패', color: '#efbfc9', ink: '#793d4c' },
    { name: '기타', color: '#d5c7ed', ink: '#594379' },
];

function installationDashboardData(rows, devices = []) {
    const groups = new Map(devices.map(name => [name, { name, counts: [0, 0, 0, 0, 0], total: 0 }]));
    for (const row of rows) {
        if (!groups.has(row.device_name)) groups.set(row.device_name, { name: row.device_name, counts: [0, 0, 0, 0, 0], total: 0 });
        const group = groups.get(row.device_name);
        const status = installationStatuses.findIndex(item => item.name === row.work_status);
        const count = Number(row.record_count) || 0;
        group.counts[status < 0 ? 4 : status] += count;
        group.total += count;
    }
    const result = [...groups.values()];
    for (const group of result) {
        // Allocate tenths so the visible percentages sum to exactly 100%.
        const exact = group.counts.map(count => group.total ? count / group.total * 1000 : 0);
        const tenths = exact.map(Math.floor);
        const order = exact.map((value, index) => ({ index, fraction: value - tenths[index] }))
            .sort((a, b) => b.fraction - a.fraction);
        const remainder = group.total ? 1000 - tenths.reduce((sum, value) => sum + value, 0) : 0;
        for (let i = 0; i < remainder; i += 1) tenths[order[i].index] += 1;
        group.percentages = tenths.map(value => value / 10);
    }
    const total = result.reduce((sum, group) => sum + group.total, 0);
    const complete = result.reduce((sum, group) => sum + group.counts[0], 0);
    return { groups: result, total, complete, incomplete: total - complete, percent: total ? complete / total * 100 : 0 };
}

function renderInstallationDashboard(rows, devices = []) {
    const get = id => document.getElementById(id);
    const element = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };
    const format = value => `${Number(value.toFixed(1))}%`;
    const chart = get('deviceStatusChart');
    chart.replaceChildren();
    get('statusLegend').replaceChildren();
    get('statusTable').replaceChildren();
    chart.hidden = true;
    get('statusDetails').hidden = true;
    const summary = rows ? installationDashboardData(rows, devices) : null;
    get('completionRing').style.setProperty('--completion', `${summary?.percent || 0}%`);
    get('completionPercent').textContent = summary?.total ? format(summary.percent) : '—';
    get('completionCounts').textContent = summary ? `완료 ${summary.complete}건 · 미완료 ${summary.incomplete}건` : '현황을 불러오지 못했습니다';
    get('completionRing').setAttribute('aria-label', summary?.total ? `전체 ${summary.total}건 중 설치 완료 ${summary.complete}건, ${format(summary.percent)}. 미완료 ${summary.incomplete}건.` : '설치 완료율 데이터 없음');
    get('dashboardTotal').textContent = summary ? `전체 ${summary.total.toLocaleString()}건` : '— 건';
    get('dashboardMessage').hidden = Boolean(summary?.total);
    get('dashboardMessage').textContent = summary ? '아직 등록된 설치 기록이 없습니다. 기록을 등록하면 현황이 표시됩니다.' : '현황을 불러오지 못했습니다. 새로고침 후 다시 확인해 주세요.';
    for (const status of installationStatuses) {
        const item = element('span', 'status-legend-item', status.name);
        const dot = element('i');
        dot.style.background = status.color;
        dot.setAttribute('aria-hidden', 'true');
        item.prepend(dot);
        get('statusLegend').append(item);
    }
    if (!summary?.total) return;
    chart.hidden = false;
    get('statusDetails').hidden = false;
    const plot = element('div', 'device-chart');
    plot.style.setProperty('--device-count', summary.groups.length);
    plot.style.setProperty('--populated-device-count', summary.groups.filter(group => group.total > 0).length);
    const grid = element('div', 'chart-grid');
    grid.setAttribute('aria-hidden', 'true');
    for (const percent of [100, 75, 50, 25, 0]) {
        const line = element('div', 'chart-grid-line');
        line.style.top = `${100 - percent}%`;
        line.append(element('span', '', `${percent}%`));
        grid.append(line);
    }
    plot.append(grid);
    const columns = element('div', 'chart-columns');
    for (const group of summary.groups) {
        const column = element('div', group.total ? 'device-column' : 'device-column device-column-empty');
        const stack = element('div', 'device-stack');
        stack.setAttribute('role', 'group');
        const description = group.counts.map((count, i) => `${installationStatuses[i].name} ${count}건 (${format(group.percentages[i])})`).join(', ');
        stack.setAttribute('aria-label', `${group.name}: ${group.total ? description : '등록 기록 없음'}`);
        stack.title = `${group.name} · ${group.total}건\n${description}`;
        if (!group.total) stack.append(element('span', 'device-no-records', '기록 없음'));
        const callouts = [];
        let cumulative = 0;
        group.counts.forEach((count, index) => {
            if (!count) return;
            const status = installationStatuses[index];
            const segment = element('button', 'status-segment');
            segment.type = 'button';
            segment.style.height = `${count / group.total * 100}%`;
            segment.style.background = status.color;
            segment.style.color = status.ink;
            segment.title = `${group.name} · ${status.name}: ${count}건 (${format(group.percentages[index])})`;
            segment.setAttribute('aria-label', `${group.name} ${status.name} ${count}건 목록 보기`);
            segment.setAttribute('aria-haspopup', 'dialog');
            segment.addEventListener('click', () => openInstallationPopup(group.name, status.name));
            if (group.percentages[index] >= 8) segment.append(element('strong', '', format(group.percentages[index])));
            else callouts.push({ index, center: cumulative + count / group.total * 50 });
            cumulative += count / group.total * 100;
            stack.append(segment);
        });
        // Reserve readable positions for thin slices, including several adjacent slices.
        callouts.forEach((item, index) => { item.position = Math.max(item.center, index ? callouts[index - 1].position + 11 : 5); });
        for (let index = callouts.length - 1; index >= 0; index--) {
            callouts[index].position = Math.min(callouts[index].position, index === callouts.length - 1 ? 95 : callouts[index + 1].position - 11);
        }
        for (const item of callouts) {
            const status = installationStatuses[item.index];
            const small = element('button', 'small-status-label', `→${format(group.percentages[item.index])}`);
            small.type = 'button';
            small.style.bottom = `${item.position}%`;
            small.style.color = status.ink;
            small.style.background = status.color;
            small.title = `${status.name} ${group.counts[item.index]}건`;
            small.setAttribute('aria-label', `${group.name} ${status.name} ${format(group.percentages[item.index])} 목록 보기`);
            small.setAttribute('aria-haspopup', 'dialog');
            small.addEventListener('click', () => openInstallationPopup(group.name, status.name));
            stack.append(small);
        }
        const label = element('div', 'device-axis-label');
        label.append(element('strong', '', group.name));
        const counts = element('div', 'device-count-summary');
        counts.append(element('span', 'device-total-count', `${group.total.toLocaleString()}건${group.total ? ' =' : ''}`));
        group.counts.forEach((count, index) => {
            if (!count) return;
            const status = installationStatuses[index];
            const item = element('button', 'device-status-count');
            item.type = 'button';
            item.title = `${status.name} ${count}건`;
            item.setAttribute('aria-label', `${group.name} ${status.name} ${count}건 목록 보기`);
            item.setAttribute('aria-haspopup', 'dialog');
            const dot = element('i');
            dot.style.background = status.color;
            dot.setAttribute('aria-hidden', 'true');
            item.append(dot, element('span', '', `${count.toLocaleString()}건`));
            item.addEventListener('click', () => openInstallationPopup(group.name, status.name));
            counts.append(item);
        });
        label.append(counts);
        column.append(stack, label);
        columns.append(column);
    }
    plot.append(columns);
    chart.append(plot);
    const table = element('table');
    const caption = element('caption', '', '장치별 작업상태 건수와 비율');
    table.append(caption);
    const head = element('tr');
    for (const text of ['장치명', '전체', ...installationStatuses.map(status => status.name)]) {
        const th = element('th', '', text);
        th.scope = 'col';
        head.append(th);
    }
    const thead = element('thead');
    thead.append(head);
    table.append(thead);
    const body = element('tbody');
    for (const group of summary.groups) {
        const row = element('tr');
        const name = element('th', '', group.name);
        name.scope = 'row';
        row.append(name, element('td', '', `${group.total}건`));
        group.counts.forEach((count, index) => row.append(element('td', '', `${count}건 · ${format(group.percentages[index])}`)));
        body.append(row);
    }
    table.append(body);
    get('statusTable').append(table);
}

function appendInstallationReportChart(parent, selectedDevice = '') {
    const source = document.getElementById('deviceStatusChart');
    const section = document.createElement('section');
    section.className = 'print-status-dashboard';
    const heading = document.createElement('h2');
    heading.className = 'print-section-title';
    heading.textContent = '장치별 작업 현황';
    const caption = document.createElement('p');
    caption.className = 'print-status-caption';
    caption.textContent = `전체 등록 기간 기준 · ${selectedDevice || '전체 장비'} · 작업상태 비율`;
    section.append(heading, caption);
    const legend = document.createElement('div');
    legend.className = 'status-legend';
    for (const item of document.getElementById('statusLegend').children) legend.append(item.cloneNode(true));
    section.append(legend);
    // Clone the displayed dashboard so counts, colors and rounding match the screen.
    const columns = [...source.querySelectorAll('.device-column')].filter(column =>
        !selectedDevice || column.querySelector('.device-axis-label strong').textContent === selectedDevice);
    if (!columns.length) {
        const empty = document.createElement('p');
        empty.textContent = '표시할 작업 현황이 없습니다.';
        section.append(empty);
    }
    // Keep every device visible on paper instead of clipping a horizontal scroll area.
    for (let offset = 0; offset < columns.length; offset += 4) {
        const group = columns.slice(offset, offset + 4);
        const plot = document.createElement('div');
        plot.className = 'device-chart';
        plot.style.setProperty('--device-count', group.length);
        plot.append(source.querySelector('.chart-grid').cloneNode(true));
        const row = document.createElement('div');
        row.className = 'chart-columns';
        for (const column of group) {
            const copy = column.cloneNode(true);
            for (const button of copy.querySelectorAll('button')) {
                const label = document.createElement('div');
                label.className = button.className;
                label.style.cssText = button.style.cssText;
                while (button.firstChild) label.append(button.firstChild);
                button.replaceWith(label);
            }
            row.append(copy);
        }
        plot.append(row);
        section.append(plot);
    }
    parent.append(section);
}

function popupCurrentVersion(record) {
    const main = record.upgrade_version || record.existing_version || '미입력';
    if (record.device_name !== 'SMU02C + Door LCD') return main;
    const door = record.door_upgrade_version || record.door_existing_version || '미입력';
    return `SMU02C: ${main} / Door LCD: ${door}`;
}

let installationPopupSequence = 0;

function closeInstallationPopup() {
    installationPopupSequence += 1;
    const dialog = document.getElementById('installationPopup');
    if (dialog?.open) dialog.close();
    dialog?.querySelector('tbody')?.replaceChildren();
    dialog?.querySelector('.popup-rack-detail')?.replaceChildren();
}

function showInstallationRacks(dialog, record, trigger) {
    const tableWrap = dialog.querySelector('.popup-table-wrap');
    const detail = dialog.querySelector('.popup-rack-detail');
    const message = dialog.querySelector('.popup-message');
    const previousMessage = message.textContent;
    const previousScroll = dialog.scrollTop;
    tableWrap.hidden = true;
    detail.hidden = false;
    detail.replaceChildren();
    const back = document.createElement('button');
    back.type = 'button';
    back.className = 'popup-rack-back';
    back.textContent = '← 목록으로';
    back.addEventListener('click', () => {
        detail.hidden = true;
        detail.replaceChildren();
        tableWrap.hidden = false;
        message.textContent = previousMessage;
        trigger.focus({ preventScroll: true });
        dialog.scrollTop = previousScroll;
    });
    const heading = document.createElement('h3');
    heading.textContent = record.site_name || '설치장소 미입력';
    const list = document.createElement('dl');
    list.className = 'popup-rack-list';
    for (let index = 0; index < record.rack_count; index += 1) {
        const card = document.createElement('div');
        const name = document.createElement('dt');
        name.textContent = record.rack_names?.[index] || `Rack ${String(index + 1).padStart(2, '0')}`;
        const count = document.createElement('dd');
        count.textContent = `모듈 ${record.module_counts?.[index] ?? '미입력'}개`;
        card.append(name, count);
        list.append(card);
    }
    message.textContent = `Rack ${record.rack_count}식 · Rack별 모듈 구성`;
    detail.append(back, heading, list);
    const stored = document.createElement('p');
    stored.textContent = `보관 모듈 수: ${record.stored_module_count ?? 0}대`;
    detail.append(stored);
    dialog.scrollTop = 0;
    back.focus({ preventScroll: true });
}

async function openInstallationPopup(device, statusName) {
    let dialog = document.getElementById('installationPopup');
    if (!dialog) {
        dialog = document.createElement('dialog');
        dialog.id = 'installationPopup';
        dialog.className = 'installation-popup';
        dialog.setAttribute('aria-labelledby', 'installationPopupTitle');
        dialog.innerHTML = '<header class="popup-heading"><div><p class="eyebrow">INSTALLATION LIST</p><h2 id="installationPopupTitle"></h2><p class="popup-subtitle"></p></div><button class="popup-close" type="button" aria-label="목록 닫기" autofocus>×</button></header><p class="popup-message" role="status" aria-live="polite"></p><div class="popup-table-wrap"><table><thead><tr><th scope="col">장비명</th><th scope="col">설치장소(국소)</th><th scope="col">작업상태</th><th scope="col">현재 설치된 버전</th></tr></thead><tbody></tbody></table></div>';
        document.body.append(dialog);
        const rackDetail = document.createElement('section');
        rackDetail.className = 'popup-rack-detail';
        rackDetail.setAttribute('aria-label', 'Rack별 이름과 모듈 수');
        rackDetail.hidden = true;
        dialog.append(rackDetail);
        dialog.querySelector('.popup-close').addEventListener('click', closeInstallationPopup);
        dialog.addEventListener('close', () => {
            installationPopupSequence += 1;
            document.body.classList.remove('installation-popup-open');
            dialog.querySelector('tbody').replaceChildren();
            dialog.querySelector('.popup-rack-detail').replaceChildren();
        });
        dialog.addEventListener('click', event => {
            if (event.target !== dialog) return;
            const bounds = dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeInstallationPopup();
        });
    }
    const request = ++installationPopupSequence;
    const status = installationStatuses.find(item => item.name === statusName);
    dialog.style.setProperty('--popup-color', status?.color || '#d5c7ed');
    dialog.style.setProperty('--popup-ink', status?.ink || '#594379');
    dialog.querySelector('h2').textContent = device;
    dialog.querySelector('.popup-subtitle').textContent = `${statusName} · 전체 기간`;
    const message = dialog.querySelector('.popup-message');
    const table = dialog.querySelector('table');
    const body = dialog.querySelector('tbody');
    dialog.querySelector('.popup-table-wrap').hidden = false;
    dialog.querySelector('.popup-rack-detail').hidden = true;
    dialog.querySelector('.popup-rack-detail').replaceChildren();
    body.replaceChildren();
    table.hidden = true;
    message.textContent = '목록을 불러오는 중입니다…';
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('installation-popup-open');
    try {
        const params = new URLSearchParams({ action: 'dashboard_records', device, work_status: statusName });
        const response = await authenticatedFetch(`api.php?${params}`, { headers: { Accept: 'application/json' } });
        const data = await response.json();
        if (request !== installationPopupSequence || !dialog.open) return;
        if (!response.ok || !Array.isArray(data.records)) throw new Error(data.error || '목록을 불러오지 못했습니다.');
        for (const record of data.records) {
            const row = document.createElement('tr');
            const currentVersion = popupCurrentVersion(record);
            for (const [index, value] of [record.device_name, record.site_name || '미입력', record.work_status, currentVersion].entries()) {
                const cell = document.createElement('td');
                if (index === 2) {
                    const badge = document.createElement('span');
                    badge.className = 'popup-status';
                    badge.textContent = value;
                    cell.append(badge);
                    if (record.work_status === '방문예정') {
                        const schedule = document.createElement('p');
                        schedule.textContent = visitScheduleDisplay(record);
                        cell.append(schedule);
                    }
                } else cell.textContent = value;
                if (index === 1) {
                    const rackButton = document.createElement('button');
                    rackButton.type = 'button';
                    rackButton.className = 'popup-rack-button';
                    rackButton.textContent = `Rack ${record.rack_count}식`;
                    rackButton.setAttribute('aria-label', `${record.device_name} ${record.site_name || '설치장소 미입력'} Rack ${record.rack_count}식 상세 보기`);
                    rackButton.addEventListener('click', () => showInstallationRacks(dialog, record, rackButton));
                    cell.append(rackButton);
                }
                row.append(cell);
            }
            body.append(row);
        }
        table.hidden = !data.records.length;
        message.textContent = data.records.length ? `총 ${data.records.length.toLocaleString()}건` : '해당 장비와 작업상태의 설치 정보가 없습니다.';
    } catch (error) {
        if (request === installationPopupSequence && dialog.open) message.textContent = error.message;
    }
}
