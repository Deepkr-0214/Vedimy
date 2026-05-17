import { AppState } from '../core/state.js';
import { api } from '../core/api.js';
import { showToast } from '../components/toast.js';

if (!AppState.getToken()) window.location.href = '/pages/login.html';
const user = AppState.getUser();
if (user?.role === 'student') window.location.href = '/pages/dashboard.html';

let selectedUserId = null;
let selectedUserName = null;
let selectedExamId = null;
let selectedRoomId = null;
let coordSocket = null;

// Cumulative per-user warning tally (live, resets when exam changes)
const userWarningCounts = {};

// ─── Load exams ────────────────────────────────────────────────────────────────
async function loadExams() {
  const select = document.getElementById('exam-select');
  try {
    const exams = await api.get('/coordinator/exams');
    select.innerHTML = '<option value="">-- Select Exam --</option>';
    exams.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.id; opt.textContent = e.title;
      if (e.room_id) opt.dataset.roomId = e.room_id;
      select.appendChild(opt);
    });
  } catch(e) { showToast('Failed to load exams', 'error'); }
}

// ─── Load violation feed ────────────────────────────────────────────────────────
async function loadMonitorData(examId) {
  try {
    const data = await api.get(`/coordinator/monitor/${examId}`);
    document.getElementById('stat-violations').textContent = data.violation_count;
    const feed = document.getElementById('violation-feed');
    feed.innerHTML = data.violations.map(v => `
      <div class="violation-item">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="color:${v.severity==='critical'?'var(--accent-danger)':v.severity==='severe'?'var(--accent-warning)':'var(--text-primary)'}">
            ${v.type} <span style="font-size:0.72rem;opacity:0.7;">(${v.severity || 'warning'})</span>
          </span>
          <div class="time">${new Date(v.timestamp).toLocaleTimeString()}</div>
        </div>
        <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:2px;">User: ${(v.user_id||'').slice(0,8)}…</div>
        ${v.screenshot ? `<img src="${v.screenshot}" style="width:100%; max-height:100px; object-fit:cover; margin-top:0.5rem; border-radius:4px; border:1px solid var(--border);">` : ''}
      </div>
    `).join('') || '<div style="color:var(--text-secondary);font-size:0.8rem;">No violations yet</div>';
  } catch(e) {}
}

// ─── Load live joined participants ─────────────────────────────────────────────
async function loadLiveParticipants(roomId) {
  if (!roomId) return;
  try {
    const participants = await api.get(`/rooms/${roomId}/participants/live`);
    document.getElementById('stat-active').textContent = participants.length;
    const panel = document.getElementById('live-participants-list');
    if (!panel) return;
    if (!participants.length) {
      panel.innerHTML = '<div style="color:var(--text-secondary);font-size:0.8rem;padding:0.5rem;">No active participants</div>';
      return;
    }
    panel.innerHTML = participants.map(p => {
      const joinT = p.join_time ? new Date(p.join_time).toLocaleTimeString() : '—';
      const faceIcon = p.face_check_passed === true ? '✅' : p.face_check_passed === false ? '❌' : '—';
      return `
        <div style="padding:0.6rem 0; border-bottom:1px solid var(--border); font-size:0.82rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:600;">${p.name}</span>
            <span title="Face verified">${faceIcon}</span>
          </div>
          <div style="color:var(--text-secondary);margin-top:2px;">${p.email}</div>
          <div style="color:var(--text-secondary);font-size:0.75rem;">Joined: ${joinT}</div>
        </div>
      `;
    }).join('');
  } catch(e) {}
}

// ─── Render candidates list ─────────────────────────────────────────────────────
function renderCandidates(candidates) {
  const list = document.getElementById('candidates-list');
  document.getElementById('stat-active').textContent = candidates.length;
  list.innerHTML = candidates.map(c => {
    const warns = userWarningCounts[c.user_id] || c.violations || 0;
    return `
    <div class="candidate-item" data-uid="${c.user_id}" style="display:flex;align-items:center;padding:0.5rem;border-bottom:1px solid var(--border);">
      <div class="pulse-dot ${warns > 2 ? 'red' : warns > 0 ? 'amber' : 'green'}" style="margin-right:0.5rem;" onclick="selectCandidate('${c.user_id}','${c.name}','${c.email||''}')"></div>
      <div style="flex:1;min-width:0;cursor:pointer;" onclick="selectCandidate('${c.user_id}','${c.name}','${c.email||''}')">
        <div class="candidate-name" style="font-weight:600;">${c.name}</div>
        ${c.email ? `<div style="font-size:0.72rem;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${c.email}</div>` : ''}
      </div>
      <div style="display:flex;align-items:center;gap:0.5rem;">
        <span class="candidate-badge ${warns > 2 ? 'badge-crit' : warns > 0 ? 'badge-warn' : 'badge-ok'}">
          ${warns} warns
        </span>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Send Warning" onclick="event.stopPropagation(); window.quickWarn('${c.user_id}')">⚠️</button>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Remove Candidate" onclick="event.stopPropagation(); window.quickRemove('${c.user_id}')">🚫</button>
      </div>
    </div>
  `}).join('');
}

// ─── Select candidate ───────────────────────────────────────────────────────────
window.selectCandidate = (uid, name, email) => {
  selectedUserId = uid;
  selectedUserName = name;
  document.querySelectorAll('.candidate-item').forEach(el => {
    el.classList.toggle('selected', el.dataset.uid === uid);
  });
  const warns = userWarningCounts[uid] || 0;
  document.getElementById('selected-view').innerHTML = `
    <div style="text-align:center;padding:2rem;">
      <div style="font-size:3rem;margin-bottom:0.5rem;">👤</div>
      <h3>${name}</h3>
      ${email ? `<div style="color:var(--text-secondary);font-size:0.82rem;margin-top:0.25rem;">${email}</div>` : ''}
      <p style="color:var(--text-secondary);font-size:0.85rem;margin-top:0.5rem;">Candidate under observation</p>
      <div style="margin-top:0.75rem;padding:0.5rem 1rem;background:var(--bg-card);border-radius:8px;display:inline-block;">
        <span style="color:${warns > 2 ? 'var(--accent-danger)' : warns > 0 ? 'var(--accent-warning)' : 'var(--accent-success)'};">
          ${warns} warning${warns !== 1 ? 's' : ''} this session
        </span>
      </div>
    </div>
  `;
  document.getElementById('selected-name-label').textContent = name;
};

// ─── Exam select ────────────────────────────────────────────────────────────────
document.getElementById('exam-select').addEventListener('change', async (e) => {
  selectedExamId = e.target.value;
  if (!selectedExamId) return;
  document.getElementById('exam-status').textContent = 'Monitoring...';

  // Grab room_id from option dataset
  const opt = e.target.selectedOptions[0];
  selectedRoomId = opt?.dataset?.roomId || null;

  // Clear tally for fresh exam session
  Object.keys(userWarningCounts).forEach(k => delete userWarningCounts[k]);

  if (coordSocket) coordSocket.disconnect();
  coordSocket = io('/coordinator', { auth: { token: AppState.getToken() } });
  coordSocket.emit('join_monitor', { exam_id: selectedExamId });

  coordSocket.on('candidate_violation', ({ user_id, violation }) => {
    // Accumulate warnings per user
    userWarningCounts[user_id] = violation.warning_count || (userWarningCounts[user_id] || 0) + 1;
    const sev = violation.severity || 'warning';
    showToast(`${sev === 'critical' ? '🚨' : '⚠️'} ${violation.type} — user ${user_id.slice(0,8)} (${userWarningCounts[user_id]} warns)`, 'error');
    // Update badge on candidate row
    const row = document.querySelector(`[data-uid="${user_id}"]`);
    if (row) {
      const badge = row.querySelector('.candidate-badge');
      const dot   = row.querySelector('.pulse-dot');
      const warns = userWarningCounts[user_id];
      if (badge) { badge.textContent = `${warns} warns`; badge.className = `candidate-badge ${warns > 2 ? 'badge-crit' : 'badge-warn'}`; }
      if (dot)   { dot.className   = `pulse-dot ${warns > 2 ? 'red' : 'amber'}`; }
    }
    loadMonitorData(selectedExamId);
  });

  coordSocket.on('live_stats', ({ active_count, violation_count }) => {
    document.getElementById('stat-active').textContent = active_count;
    document.getElementById('stat-violations').textContent = violation_count;
  });

  // ── Name change alert relayed from signaling.py ─────────────────────────────
  coordSocket.on('name_change_alert', ({ old_name, new_name, email, time }) => {
    showToast(`✏️ Name change: ${old_name} → ${new_name}`, 'warning');
    if (typeof window.pushNameChangeAlert === 'function') {
      window.pushNameChangeAlert(old_name, new_name, email, time);
    }
  });

  await loadMonitorData(selectedExamId);
  if (selectedRoomId) await loadLiveParticipants(selectedRoomId);

  // Poll every 15s
  setInterval(() => {
    loadMonitorData(selectedExamId);
    if (selectedRoomId) loadLiveParticipants(selectedRoomId);
  }, 15000);
});

// ─── Action buttons ─────────────────────────────────────────────────────────────
document.getElementById('action-warn').addEventListener('click', async () => {
  if (!selectedUserId || !selectedExamId) { showToast('Select a candidate first', 'error'); return; }
  await api.post('/coordinator/action', {
    exam_id: selectedExamId, target_user_id: selectedUserId,
    action_type: 'sent_warning', notes: 'Manual warning from coordinator'
  });
  coordSocket?.emit('send_warning', { user_id: selectedUserId, message: 'Warning from coordinator' });
  showToast('Warning sent', 'success');
});

document.getElementById('action-remove').addEventListener('click', async () => {
  if (!selectedUserId || !selectedExamId) { showToast('Select a candidate first', 'error'); return; }
  await window.quickRemove(selectedUserId);
});

window.quickWarn = async (userId) => {
  if (!selectedExamId) return;
  await api.post('/coordinator/action', {
    exam_id: selectedExamId, target_user_id: userId,
    action_type: 'sent_warning', notes: 'Quick warning from coordinator'
  });
  coordSocket?.emit('send_warning', { user_id: userId, message: 'Warning from coordinator' });
  showToast('Warning sent', 'success');
};

window.quickRemove = async (userId) => {
  if (!selectedExamId) return;
  if (!confirm('Remove this candidate from the exam?')) return;
  await api.post('/coordinator/action', {
    exam_id: selectedExamId, target_user_id: userId,
    action_type: 'removed', notes: 'Quick removed by coordinator'
  });
  coordSocket?.emit('remove_user', { user_id: userId });
  showToast('Candidate removed', 'success');
  document.querySelector(`[data-uid="${userId}"]`)?.remove();
  if (selectedUserId === userId) {
    selectedUserId = null;
    document.getElementById('selected-name-label').textContent = '—';
  }
};

document.getElementById('action-block')?.addEventListener('click', async () => {
  if (!selectedUserId || !selectedExamId) { showToast('Select a candidate first', 'error'); return; }
  if (!confirm('Permanently block this candidate from the exam room?')) return;
  try {
    await api.post('/coordinator/action', {
      exam_id: selectedExamId, target_user_id: selectedUserId,
      action_type: 'blocked', notes: 'Blocked by coordinator'
    });
    coordSocket?.emit('remove_user', { user_id: selectedUserId });
    showToast('Candidate blocked', 'success');
    document.querySelector(`[data-uid="${selectedUserId}"]`)?.remove();
    selectedUserId = null;
    document.getElementById('selected-name-label').textContent = '—';
  } catch(e) { showToast('Failed to block', 'error'); }
});

// ─── Auto-submit all ────────────────────────────────────────────────────────────
document.getElementById('action-auto-submit-all')?.addEventListener('click', async () => {
  if (!selectedExamId) { showToast('Select an exam first', 'error'); return; }
  if (!confirm('Force auto-submit for ALL active candidates? This cannot be undone.')) return;
  try {
    // Emit exam_terminated to the entire exam room
    coordSocket?.emit('terminate_exam', { exam_id: selectedExamId, reason: 'Terminated by coordinator' });
    showToast('Auto-submit triggered for all candidates', 'success');
  } catch(e) { showToast('Failed to trigger auto-submit', 'error'); }
});

loadExams();

// Refresh-live custom event (fired from the HTML Refresh button)
window.addEventListener('coord:refresh-live', () => {
  if (selectedRoomId) loadLiveParticipants(selectedRoomId);
  else showToast('Select an exam first', 'error');
});
