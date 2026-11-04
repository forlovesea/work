const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
class Node {
    constructor(tag = 'div') {
        this.tag = tag; this.children = []; this.className = ''; this.textContent = '';
        this.style = {
            setProperty(key, value) { this[key] = value; },
            get cssText() { return JSON.stringify(Object.fromEntries(Object.keys(this).filter(key => key !== 'cssText' && typeof this[key] !== 'function').map(key => [key, this[key]]))); },
            set cssText(value) { Object.assign(this, JSON.parse(value)); },
        };
    }
    append(...nodes) { for (const node of nodes) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = this; this.children.push(node); } }
    prepend(node) { this.children.unshift(node); node.parent = this; }
    replaceChildren() { this.children = []; }
    setAttribute() {}
    addEventListener() {}
    get firstChild() { return this.children[0]; }
    cloneNode(deep) { const copy = new Node(this.tag); copy.className = this.className; copy.textContent = this.textContent; Object.assign(copy.style, this.style); if (deep) copy.append(...this.children.map(node => node.cloneNode(true))); return copy; }
    replaceWith(node) { const index = this.parent.children.indexOf(this); this.parent.children[index] = node; node.parent = this.parent; }
    querySelectorAll(selector) {
        const all = this.children.flatMap(node => [node, ...node.querySelectorAll('*')]);
        if (selector === '*') return all;
        return all.filter(node => selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag === selector);
    }
    querySelector(selector) { if (selector.includes(' ')) { const [parent, child] = selector.split(' '); return this.querySelector(parent)?.querySelector(child); } return this.querySelectorAll(selector)[0]; }
}
const nodes = new Map();
const context = vm.createContext({ document: {
    createElement: tag => new Node(tag),
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
} });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../public/assets/dashboard.js'), 'utf8'), context);
const devices = ['A', 'B', 'C', 'D', 'E'];
context.renderInstallationDashboard(devices.map(device_name => ({ device_name, work_status: '작업완료', record_count: 1 })), devices);
const all = new Node();
context.appendInstallationReportChart(all);
assert.equal(all.querySelectorAll('.device-column').length, 5);
assert.equal(all.querySelectorAll('.device-chart').length, 2);
assert.equal(all.querySelectorAll('button').length, 0);
const filtered = new Node();
context.appendInstallationReportChart(filtered, 'B');
assert.equal(filtered.querySelectorAll('.device-column').length, 1);
assert.equal(filtered.querySelector('.device-axis-label strong').textContent, 'B');
assert.equal(filtered.querySelector('.status-segment').style.background, '#a8dfcc');
assert.equal(nodes.get('deviceStatusChart').querySelectorAll('.device-column').length, 5);
assert.equal(nodes.get('deviceStatusChart').querySelectorAll('button').length, 10);
context.renderInstallationDashboard([], []);
const empty = new Node();
context.appendInstallationReportChart(empty);
assert.equal(empty.querySelectorAll('.device-column').length, 0);
assert.ok(empty.querySelectorAll('p').some(node => node.textContent === '표시할 작업 현황이 없습니다.'));
console.log('PASS: print chart matches dashboard, device filter, page-width grouping, static labels and unchanged live chart');
