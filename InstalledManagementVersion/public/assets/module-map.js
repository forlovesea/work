// Regional anchors are schematic. Address counts are grouped by province, not geocoded.
const moduleMapRegions = [
    ['서울', ['서울', '서울시', '서울특별시'], 126.98, 37.57, 0, 16],
    ['인천', ['인천', '인천시', '인천광역시'], 126.70, 37.46, 0, 62],
    ['경기', ['경기', '경기도'], 127.25, 37.30, 0, 108],
    ['충남', ['충남', '충청남도'], 126.80, 36.60, 0, 154],
    ['세종', ['세종', '세종시', '세종특별자치시'], 127.29, 36.48, 0, 200],
    ['대전', ['대전', '대전시', '대전광역시'], 127.38, 36.35, 0, 246],
    ['전북', ['전북', '전라북도', '전북특별자치도'], 127.10, 35.72, 0, 292],
    ['광주', ['광주', '광주시', '광주광역시'], 126.85, 35.16, 0, 338],
    ['전남', ['전남', '전라남도'], 126.90, 34.75, 0, 384],
    ['강원', ['강원', '강원도', '강원특별자치도'], 128.25, 37.75, 325, 16],
    ['충북', ['충북', '충청북도'], 127.75, 36.80, 325, 62],
    ['경북', ['경북', '경상북도'], 128.75, 36.35, 325, 108],
    ['대구', ['대구', '대구시', '대구광역시'], 128.60, 35.87, 325, 154],
    ['울산', ['울산', '울산시', '울산광역시'], 129.31, 35.54, 325, 200],
    ['부산', ['부산', '부산시', '부산광역시'], 129.07, 35.18, 325, 246],
    ['경남', ['경남', '경상남도'], 128.10, 35.30, 325, 292],
    ['제주', ['제주', '제주도', '제주시', '제주특별자치도'], 126.53, 33.38, 325, 384],
];

function moduleMapRegion(address) {
    const first = String(address || '').trim().replace(/^대한민국\s+/, '').split(/\s+/)[0];
    return moduleMapRegions.find(region => region[1].includes(first))?.[0] || '주소 미분류';
}

function moduleMapData(records) {
    const groups = new Map([...moduleMapRegions.map(region => region[0]), '주소 미분류']
        .map(name => [name, { name, installed: 0, stored: 0, total: 0, records: 0, addresses: new Map() }]));
    for (const record of records) {
        const address = String(record.address || '').trim() || '주소 미입력';
        const group = groups.get(moduleMapRegion(address));
        const installed = Math.max(0, Number(record.installed) || 0);
        const stored = Math.max(0, Number(record.stored) || 0);
        group.installed += installed;
        group.stored += stored;
        group.total += installed + stored;
        group.records += 1;
        const item = group.addresses.get(address) || { address, installed: 0, stored: 0, total: 0, records: 0 };
        item.installed += installed;
        item.stored += stored;
        item.total += installed + stored;
        item.records += 1;
        group.addresses.set(address, item);
    }
    return groups;
}

function renderModuleMap(records) {
    const get = id => document.getElementById(id);
    const canvas = get('moduleMapCanvas');
    const details = get('moduleMapDetails');
    const previous = details.dataset.region;
    canvas.replaceChildren();
    details.hidden = true;
    get('moduleMapUnknown').hidden = true;
    get('moduleMapAddresses').replaceChildren();
    if (!Array.isArray(records)) {
        get('moduleMapTotal').textContent = '— 개';
        get('moduleMapMessage').textContent = '현황을 불러오지 못했습니다. 새로고침해 주세요.';
        return;
    }
    const groups = moduleMapData(records);
    const format = value => value.toLocaleString('ko-KR');
    get('moduleMapTotal').textContent = `${format([...groups.values()].reduce((sum, group) => sum + group.total, 0))}개`;
    get('moduleMapMessage').textContent = records.length ? '지역을 누르면 주소별 수량을 볼 수 있습니다.' : '등록된 설치 기록이 없습니다.';
    const show = (name, open = true) => {
        const group = groups.get(name);
        details.dataset.region = name;
        details.hidden = false;
        details.open = open;
        get('moduleMapSelection').textContent = `${name} · ${format(group.total)}개 · ${format(group.records)}건`;
        const list = get('moduleMapAddresses');
        list.replaceChildren();
        for (const item of [...group.addresses.values()].sort((a, b) => b.total - a.total || a.address.localeCompare(b.address, 'ko'))) {
            const row = document.createElement('p');
            const address = document.createElement('strong');
            address.textContent = item.address;
            const count = document.createElement('span');
            count.textContent = `총 ${format(item.total)}개 (설치 ${format(item.installed)} + 보관 ${format(item.stored)}) · ${item.records}건`;
            row.append(address, count);
            list.append(row);
        }
        if (!group.records) list.textContent = '이 지역에 등록된 기록이 없습니다.';
        canvas.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.region === name)));
    };
    const ns = 'http://www.w3.org/2000/svg';
    const lines = document.createElementNS(ns, 'svg');
    lines.setAttribute('viewBox', '0 0 420 450');
    lines.setAttribute('aria-hidden', 'true');
    canvas.append(lines);
    const max = Math.max(1, ...[...groups.values()].map(group => group.total));
    for (const [name, , lon, lat, x, y] of moduleMapRegions) {
        const group = groups.get(name);
        const px = 110 + (lon - 125) * 48;
        const py = 25 + (38.7 - lat) * 68;
        const line = document.createElementNS(ns, 'path');
        line.setAttribute('d', `M${x ? x : 95},${y + 19} L${x ? 310 : 105},${y + 19} L${px},${py}`);
        lines.append(line);
        const dot = document.createElementNS(ns, 'circle');
        dot.setAttribute('cx', px);
        dot.setAttribute('cy', py);
        dot.setAttribute('r', group.total ? 3 + Math.sqrt(group.total / max) * 6 : 2);
        dot.setAttribute('class', group.total ? 'has-modules' : 'no-modules');
        lines.append(dot);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `module-map-region${group.total ? ' has-modules' : ''}`;
        button.style.left = `${x / 420 * 100}%`;
        button.style.top = `${y / 450 * 100}%`;
        button.dataset.region = name;
        button.setAttribute('aria-pressed', 'false');
        button.setAttribute('aria-controls', 'moduleMapDetails');
        button.setAttribute('aria-label', `${name} 총 ${format(group.total)}개, 설치 ${format(group.installed)}개, 보관 ${format(group.stored)}개. 주소별 상세 보기`);
        const label = document.createElement('span');
        label.textContent = name;
        const count = document.createElement('strong');
        count.textContent = `${format(group.total)}개`;
        button.append(label, count);
        button.addEventListener('click', () => show(name));
        canvas.append(button);
    }
    const unknown = groups.get('주소 미분류');
    if (unknown.records) {
        const button = get('moduleMapUnknown');
        button.hidden = false;
        button.textContent = `주소 미분류 ${format(unknown.total)}개 · ${unknown.records}건 ›`;
        button.onclick = () => show('주소 미분류');
    }
    if (previous && groups.has(previous)) show(previous, details.open);
}
