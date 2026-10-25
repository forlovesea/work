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
        const column = element('div', 'device-column');
        const stack = element('div', 'device-stack');
        stack.setAttribute('role', 'group');
        const description = group.counts.map((count, i) => `${installationStatuses[i].name} ${count}건 (${format(group.percentages[i])})`).join(', ');
        stack.setAttribute('aria-label', `${group.name}: ${group.total ? description : '등록 기록 없음'}`);
        stack.title = `${group.name} · ${group.total}건\n${description}`;
        if (!group.total) stack.append(element('span', 'device-no-records', '기록 없음'));
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
            stack.append(segment);
        });
        const label = element('div', 'device-axis-label');
        label.append(element('strong', '', group.name), element('span', '', `${group.total.toLocaleString()}건`));
        group.counts.forEach((count, index) => {
            if (!count || group.percentages[index] >= 8) return;
            const small = element('button', 'small-status-label', `${installationStatuses[index].name} ${format(group.percentages[index])}`);
            small.type = 'button';
            small.setAttribute('aria-haspopup', 'dialog');
            small.addEventListener('click', () => openInstallationPopup(group.name, installationStatuses[index].name));
            small.style.color = installationStatuses[index].ink;
            label.append(small);
        });
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

let installationPopupSequence = 0;

function closeInstallationPopup() {
    installationPopupSequence += 1;
    const dialog = document.getElementById('installationPopup');
    if (dialog?.open) dialog.close();
    dialog?.querySelector('tbody')?.replaceChildren();
}

async function openInstallationPopup(device, statusName) {
    let dialog = document.getElementById('installationPopup');
    if (!dialog) {
        dialog = document.createElement('dialog');
        dialog.id = 'installationPopup';
        dialog.className = 'installation-popup';
        dialog.setAttribute('aria-labelledby', 'installationPopupTitle');
        dialog.innerHTML = '<header class="popup-heading"><div><p class="eyebrow">INSTALLATION LIST</p><h2 id="installationPopupTitle"></h2><p class="popup-subtitle"></p></div><button class="popup-close" type="button" aria-label="목록 닫기" autofocus>×</button></header><p class="popup-message" role="status" aria-live="polite"></p><div class="popup-table-wrap"><table><thead><tr><th scope="col">장비명</th><th scope="col">설치장소(국소)</th><th scope="col">작업상태</th></tr></thead><tbody></tbody></table></div>';
        document.body.append(dialog);
        dialog.querySelector('.popup-close').addEventListener('click', closeInstallationPopup);
        dialog.addEventListener('close', () => {
            installationPopupSequence += 1;
            document.body.classList.remove('installation-popup-open');
            dialog.querySelector('tbody').replaceChildren();
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
            for (const [index, value] of [record.device_name, record.site_name || '미입력', record.work_status].entries()) {
                const cell = document.createElement('td');
                if (index === 2) {
                    const badge = document.createElement('span');
                    badge.className = 'popup-status';
                    badge.textContent = value;
                    cell.append(badge);
                } else cell.textContent = value;
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
