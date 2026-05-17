import { AppState } from '../core/state.js';
import { api } from '../core/api.js';
import { showToast } from '../components/toast.js';

if (!AppState.getToken()) window.location.href = '/pages/login.html';

const params = new URLSearchParams(window.location.search);
const examId = params.get('exam_id');
const roomCode = params.get('code');

let localStream = null;
let socket = null;        // conference socket
let proctoringSocket = null;
let proctoringInterval = null;
let timerInterval = null;
let warningCount = 0;
let maxWarnings = 3;
let examActive = false;
let isMuted = false;
let isVideoOff = false;
let autoSubmitCountdown = null; // auto-submit timer handle

function captureFrame(videoEl, quality = 0.7) {
  const canvas = document.createElement('canvas');
  canvas.width = videoEl.videoWidth || 320;
  canvas.height = videoEl.videoHeight || 240;
  canvas.getContext('2d').drawImage(videoEl, 0, 0);
  return canvas.toDataURL('image/jpeg', quality);
}

function startProctoring(videoEl, intervalSecs = 10) {
  proctoringSocket.emit('exam_active', { exam_id: examId });
  return setInterval(() => {
    if (!examActive) return;
    const frame = captureFrame(videoEl);
    proctoringSocket.emit('frame_check', { exam_id: examId, user_id: AppState.getUser().id, frame_base64: frame });
    document.getElementById('face-status').className = 'face-status';
    document.getElementById('face-status').textContent = '👤 Checking...';
    
    // Check if camera is disabled
    if (isVideoOff || (localStream && !localStream.getVideoTracks()[0].enabled)) {
      proctoringSocket.emit('violation', { type: 'camera_disabled', exam_id: examId, user_id: AppState.getUser().id });
    }
  }, intervalSecs * 1000);
}

function showViolationBanner(type, count) {
  const banner = document.getElementById('violation-banner');
  const msgs = {
    'no_face': '⚠️ No face detected!',
    'multiple_faces': '🚨 Multiple faces detected!',
    'unknown_face': '❌ Face not recognized!',
    'tab_switch': '⚠️ Tab switch detected!',
    'fullscreen_exit': '⚠️ Fullscreen exited!',
    'camera_disabled': '⚠️ Camera disabled!'
  };
  banner.textContent = `${msgs[type] || type} — Warning ${count}/${maxWarnings}`;
  banner.classList.add('show');
  setTimeout(() => banner.classList.remove('show'), 5000);
}

/** Start a 5-second auto-submit countdown. Only starts once. */
function startAutoSubmitCountdown() {
  if (autoSubmitCountdown) return; // already running
  let remaining = 5;
  const banner = document.getElementById('violation-banner');
  banner.textContent = `🚨 Max violations reached! Auto-submitting in ${remaining}s…`;
  banner.classList.add('show');
  autoSubmitCountdown = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(autoSubmitCountdown);
      banner.classList.remove('show');
      submitExam();
    } else {
      banner.textContent = `🚨 Max violations reached! Auto-submitting in ${remaining}s…`;
    }
  }, 1000);
}

function startTimer(durationMinutes) {
  let remaining = durationMinutes * 60;
  timerInterval = setInterval(() => {
    remaining--;
    const mins = String(Math.floor(remaining / 60)).padStart(2, '0');
    const secs = String(remaining % 60).padStart(2, '0');
    const el = document.getElementById('exam-timer');
    el.textContent = `${mins}:${secs}`;
    el.classList.toggle('warning', remaining <= 300);
    if (remaining <= 0) { clearInterval(timerInterval); submitExam(); }
  }, 1000);
}

async function submitExam() {
  clearInterval(proctoringInterval);
  clearInterval(timerInterval);
  examActive = false;
  
  // Collect answers
  const answers = {};
  document.querySelectorAll('.q-answer').forEach(el => {
    if (el.type === 'radio' && el.checked) answers[el.name] = el.value;
    else if (el.tagName === 'TEXTAREA') answers[el.dataset.qid] = el.value.trim();
  });

  try {
    if (examId) await api.post(`/exams/${examId}/submit`, { answers });
  } catch(e) {}
  
  if (roomCode) await api.post(`/rooms/${roomCode}/leave`, {}).catch(() => {});
  localStream?.getTracks().forEach(t => t.stop());
  localStorage.removeItem(`exam_answers_${examId}`);
  window.location.href = '/pages/dashboard.html';
}

function saveAnswersToStorage() {
  const answers = {};
  document.querySelectorAll('.q-answer').forEach(el => {
    if (el.type === 'radio' && el.checked) answers[el.name] = el.value;
    else if (el.tagName === 'TEXTAREA') answers[el.dataset.qid] = el.value.trim();
  });
  localStorage.setItem(`exam_answers_${examId}`, JSON.stringify(answers));
}

function loadAnswersFromStorage() {
  try {
    const saved = localStorage.getItem(`exam_answers_${examId}`);
    if (!saved) return;
    const answers = JSON.parse(saved);
    document.querySelectorAll('.q-answer').forEach(el => {
      if (el.type === 'radio') {
        if (answers[el.name] === el.value) el.checked = true;
      } else if (el.tagName === 'TEXTAREA') {
        if (answers[el.dataset.qid]) el.value = answers[el.dataset.qid];
      }
    });
  } catch (e) {
    console.warn('Failed to load answers from storage', e);
  }
}

async function init() {
  // Load exam info
  if (examId) {
    try {
      const exam = await api.get(`/exams/${examId}`);
      document.getElementById('exam-title').textContent = exam.title;
      document.getElementById('max-warnings').textContent = exam.max_warnings;
      if (exam.instructions) document.getElementById('exam-instructions').textContent = exam.instructions;
      
      if (exam.questions && exam.questions.length > 0) {
        document.getElementById('questions-pane').style.display = 'block';
        document.getElementById('questions-container').innerHTML = exam.questions.map((q, i) => `
          <div class="q-card">
            <p style="font-weight:600;margin-bottom:0.75rem;">Q${i+1}. ${q.question}</p>
            ${q.type === 'mcq' ? `
              <div class="q-options">
                ${q.options.map((opt, j) => `
                  <label><input type="radio" name="q_${i}" value="${opt[0]}" class="q-answer"> ${opt}</label>
                `).join('')}
              </div>
            ` : `
              <textarea data-qid="q_${i}" class="q-answer" style="width:100%;background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;padding:0.75rem;color:white;resize:vertical;" rows="3" placeholder="Type your answer here..."></textarea>
            `}
          </div>
        `).join('');
        
        // Feature 29: Session Recovery - Persist Answers
        loadAnswersFromStorage();
        document.querySelectorAll('.q-answer').forEach(el => {
          el.addEventListener('change', saveAnswersToStorage);
          el.addEventListener('input', saveAnswersToStorage);
        });
      }

      maxWarnings = exam.max_warnings;
      if (exam.status === 'active') {
        document.getElementById('exam-status').textContent = '🔴 LIVE';
        examActive = true;
        startTimer(exam.duration_minutes);
      }
    } catch(e) { showToast('Failed to load exam', 'error'); }
  }

  // Local camera
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  } catch(e) {
    showToast('Camera/mic required for exam', 'error');
    return;
  }

  const tile = document.createElement('div');
  tile.className = 'video-tile'; tile.id = 'tile-local';
  tile.innerHTML = `
    <video autoplay playsinline muted></video>
    <div class="name-label" style="display:flex;align-items:center;gap:0.5rem;">
      <span id="local-name-display">${AppState.getUser()?.name || 'You'}</span>
      <button id="edit-name-btn" style="background:transparent;border:none;color:var(--accent-primary);cursor:pointer;font-size:0.8rem;padding:0;" title="Change Name">✏️</button>
    </div>
    <div class="proctoring-overlay" id="proctor-overlay"></div>
  `;
  tile.querySelector('video').srcObject = localStream;
  document.getElementById('video-grid').appendChild(tile);

  // Conference socket (for name-change alerts and exam warnings from coordinator)
  // Feature 24: robust reconnect + exam blocking overlay
  const examReconnectOverlay = document.createElement('div');
  examReconnectOverlay.id = 'exam-reconnect-overlay';
  examReconnectOverlay.style.cssText = 'display:none;position:fixed;top:0;left:0;right:0;background:var(--accent-danger);color:white;text-align:center;padding:0.75rem;z-index:9999;font-weight:600;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
  examReconnectOverlay.innerHTML = `⚠️ Connection Lost. Exam paused. Reconnecting securely... <span id="exam-reconnect-attempt" style="margin-left:8px;opacity:0.8;"></span>`;
  document.body.appendChild(examReconnectOverlay);

  socket = io('/conference', {
    auth: { token: AppState.getToken() },
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 10000
  });
  socket.on('disconnect', (reason) => {
    if (reason !== 'io client disconnect') {
      examReconnectOverlay.style.display = 'flex';
      examActive = false; // pause exam during disconnect
    }
  });
  socket.on('reconnecting', (attempt) => {
    const el = document.getElementById('exam-reconnect-attempt');
    if (el) el.textContent = `Reconnect attempt ${attempt}...`;
  });
  socket.on('reconnect', () => {
    examReconnectOverlay.style.display = 'none';
    examActive = true; // resume
    showToast('✅ Reconnected securely. Exam resumed.', 'success');
  });
  socket.on('connect', () => {
    examReconnectOverlay.style.display = 'none';
    if (roomCode) {
      socket.emit('join_room', {
        room_code: roomCode,
        user_id: AppState.getUser()?.id,
        name: AppState.getUser()?.name,
        peer_id: null
      });
    }
  });
  socket.on('exam_warning', ({ message }) => {
    showToast(`⚠️ Coordinator Warning: ${message}`, 'warning');
    const banner = document.getElementById('violation-banner');
    banner.textContent = `⚠️ ${message}`;
    banner.classList.add('show');
    setTimeout(() => banner.classList.remove('show'), 6000);
  });
  socket.on('exam_paused', ({ message }) => {
    showToast(message, 'warning');
    examActive = false;
  });
  socket.on('exam_resumed', ({ message }) => {
    showToast(message, 'success');
    examActive = true;
  });

  // Proctoring socket
  proctoringSocket = io('/proctoring', { auth: { token: AppState.getToken() } });
  proctoringSocket.on('face_ok', ({ confidence }) => {
    const s = document.getElementById('face-status');
    s.className = 'face-status ok'; s.textContent = `✅ Face verified (${Math.round(confidence*100)}%)`;
    document.getElementById('proctor-overlay').className = 'proctoring-overlay ok';
  });
  proctoringSocket.on('violation_detected', ({ type, severity, warning_count }) => {
    warningCount = warning_count;
    document.getElementById('warning-count').textContent = warning_count;
    document.getElementById('face-status').className = 'face-status fail';
    // Tint severity
    const severityColors = { warning: '', severe: 'color:var(--accent-warning)', critical: 'color:var(--accent-danger)' };
    document.getElementById('face-status').textContent = severity === 'critical' ? '🚨 Critical Violation!' : '❌ Violation!';
    document.getElementById('proctor-overlay').className = `proctoring-overlay fail`;
    showViolationBanner(type, warning_count);
    if (warning_count >= maxWarnings) {
      showToast('⛔ Maximum violations reached — exam auto-submitting!', 'error');
      startAutoSubmitCountdown();
    } else if (severity === 'severe') {
      showToast(`⚠️ Severe violation (${warning_count}/${maxWarnings}). Next will auto-submit!`, 'warning');
    }
  });
  proctoringSocket.on('coordinator_present', ({ coordinator_name }) => {
    const badge = document.getElementById('coordinator-badge');
    badge.classList.add('visible');
    setTimeout(() => badge.classList.remove('visible'), 10000);
  });
  proctoringSocket.on('exam_terminated', ({ reason }) => {
    showToast('Exam terminated: ' + reason, 'error');
    setTimeout(submitExam, 3000);
  });

  if (examActive) {
    const videoEl = tile.querySelector('video');
    proctoringInterval = startProctoring(videoEl, 10);
  }

  // Tab switch detection
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && examActive) {
      const frame = tile.querySelector('video') ? captureFrame(tile.querySelector('video')) : null;
      proctoringSocket.emit('violation', { type: 'tab_switch', exam_id: examId, user_id: AppState.getUser().id, frame_base64: frame });
    }
  });

  // Fullscreen exit detection
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && examActive) {
      const frame = tile.querySelector('video') ? captureFrame(tile.querySelector('video')) : null;
      proctoringSocket.emit('violation', { type: 'fullscreen_exit', exam_id: examId, user_id: AppState.getUser().id, frame_base64: frame });
    }
  });

  // Name Change UI setup
  document.getElementById('edit-name-btn').addEventListener('click', async () => {
    const u = AppState.getUser();
    const oldName = u?.name || '';
    const newName = prompt('Enter your new display name:', oldName);
    if (!newName || newName.trim() === '' || newName.trim() === oldName) return;
    const trimmedName = newName.trim();
    try {
      await api.put('/auth/profile/name', { name: trimmedName });
      u.name = trimmedName;
      AppState.setAuth(u, AppState.getToken());
      document.getElementById('local-name-display').textContent = trimmedName;
      showToast('Name updated successfully', 'success');

      // ── Alert host via conference socket ──────────────────────────────
      if (socket && roomCode) {
        socket.emit('name_changed', {
          room_code: roomCode,
          user_id: u.id,
          old_name: oldName,
          new_name: trimmedName,
          email: u.email || 'unknown',
          host_id: null   // backend will fan-out to host_alerts room via SecurityLog
        });
      }
    } catch(e) { showToast('Failed to change name', 'error'); }
  });
}

// Controls
document.getElementById('mute-btn').addEventListener('click', () => {
  isMuted = !isMuted;
  localStream?.getAudioTracks().forEach(t => t.enabled = !isMuted);
  document.getElementById('mute-btn').textContent = isMuted ? '🔇' : '🎤';
  document.getElementById('mute-btn').classList.toggle('muted', isMuted);
});
document.getElementById('video-btn').addEventListener('click', () => {
  isVideoOff = !isVideoOff;
  localStream?.getVideoTracks().forEach(t => t.enabled = !isVideoOff);
  document.getElementById('video-btn').textContent = isVideoOff ? '📵' : '📷';
  document.getElementById('video-btn').classList.toggle('vid-off', isVideoOff);
});
document.getElementById('hand-btn').addEventListener('click', () => {
  socket?.emit('raise_hand', { room_code: roomCode, user_name: AppState.getUser().name });
  showToast('Hand raised ✋', 'info');
});
document.getElementById('submit-btn').addEventListener('click', () => {
  if (confirm('Submit exam and leave?')) submitExam();
});

init();
