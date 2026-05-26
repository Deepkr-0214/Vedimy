import { AppState } from '../core/state.js';
import { api } from '../core/api.js';
import { showToast } from '../components/toast.js';

const MIC_ON_SVG = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/><path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>`;
const MIC_OFF_SVG = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17l-1.98-1.98V5c0-1.66-1.34-3-3-3S7 3.34 7 5v.17l4.17 4.17zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.79 1.79c-.73.47-1.59.79-2.53.87V21h2v-3.08c1.39-.17 2.63-.7 3.65-1.47l2.8 2.8L21 18l-3.66-3.66L4.27 3z"/></svg>`;
const CAM_ON_SVG = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>`;
const CAM_OFF_SVG = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M21 6.5l-4 4V7c0-.55-.45-1-1-1H9.82L21 17.18V6.5zM3.27 2L2 3.27 4.73 6H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.21 0 .39-.08.55-.18L19.27 21 20.5 19.73 3.27 2zM15 16.27l-9-9V16h9v.27z"/></svg>`;

if (!AppState.getToken()) window.location.href = '/pages/login.html';

const params = new URLSearchParams(window.location.search);
const roomCode = params.get('code');
if (!roomCode) { showToast('No room code provided', 'error'); }

let localStream = null;
let socket = null;
let peerManager = null;
let isMuted = false;
let isVideoOff = false;
let isScreenSharing = false;
let participantMap = {}; // peerId → { name, muted }
let roomData = null;
let amIWaiting = false;

const ICE_SERVERS = { iceServers: [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' }
]};

class PeerManager {
  constructor(socket, stream) {
    this.peers = {};
    this.socket = socket;
    this.localStream = stream;
  }
  addPeer(peerId, initiator, name = 'User') {
    if (this.peers[peerId]) return;
    const peer = new SimplePeer({ initiator, stream: this.localStream, config: ICE_SERVERS });
    peer.on('signal', (data) => {
      const ev = data.type === 'offer' ? 'offer' : data.type === 'answer' ? 'answer' : 'ice_candidate';
      this.socket.emit(ev, { to: peerId, sdp: data });
    });
    peer.on('stream', (remoteStream) => this._renderRemote(peerId, remoteStream, name));
    peer.on('close', () => this.removePeer(peerId));
    peer.on('error', (err) => console.warn('Peer error:', err));
    this.peers[peerId] = peer;
    return peer;
  }
  signal(peerId, data) { if (this.peers[peerId]) this.peers[peerId].signal(data); }
  removePeer(peerId) {
    if (this.peers[peerId]) { this.peers[peerId].destroy(); delete this.peers[peerId]; }
    document.getElementById(`tile-${peerId}`)?.remove();
    updateGridLayout();
  }
  _renderRemote(peerId, stream, name) {
    const existing = document.getElementById(`tile-${peerId}`);
    if (existing) { existing.querySelector('video').srcObject = stream; return; }
    const tile = document.createElement('div');
    tile.className = 'video-tile'; tile.id = `tile-${peerId}`;
    tile.dataset.userId = participantMap[peerId]?.user_id || '';
    tile.innerHTML = `<video autoplay playsinline></video><div class="name-label">${name}</div>`;
    tile.querySelector('video').srcObject = stream;
    document.getElementById('video-grid').appendChild(tile);
    updateGridLayout();
  }
}

function updateGridLayout() {
  const grid = document.getElementById('video-grid');
  const count = grid.children.length;
  let cols = 1;
  if (count >= 2) cols = 2;
  if (count >= 5) cols = 3;
  if (count >= 10) cols = 4;
  grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  document.getElementById('participant-count').textContent = `${count} participant${count !== 1 ? 's' : ''}`;
}

async function init() {
  // Get room info
  if (roomCode) {
    try {
      roomData = await api.get(`/rooms/${roomCode}`);
      document.getElementById('room-title').textContent = roomData.title;
      document.getElementById('room-code').textContent = roomCode;
      
      const joinRes = await api.post(`/rooms/${roomCode}/join`, {});
      if (joinRes.status === 'waiting') {
        amIWaiting = true;
        document.getElementById('waiting-overlay').style.display = 'flex';

        // ── Waiting Room: start camera preview immediately ──────────────────
        try {
          localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
          const waitingVideo = document.getElementById('waiting-camera');
          if (waitingVideo) waitingVideo.srcObject = localStream;
        } catch(camErr) {
          showToast('Camera/mic permission denied', 'error');
          localStream = new MediaStream();
        }

        // ── Elapsed timer ───────────────────────────────────────────────────
        let waitSeconds = 0;
        const waitTimerEl = document.getElementById('waiting-timer');
        const waitTimerInterval = setInterval(() => {
          waitSeconds++;
          const m = Math.floor(waitSeconds / 60);
          const s = String(waitSeconds % 60).padStart(2, '0');
          if (waitTimerEl) waitTimerEl.textContent = `${m}:${s}`;
        }, 1000);

        // ── Mic toggle while waiting ────────────────────────────────────────
        let waitMuted = false;
        document.getElementById('waiting-mute-btn')?.addEventListener('click', () => {
          waitMuted = !waitMuted;
          localStream?.getAudioTracks().forEach(t => t.enabled = !waitMuted);
          const btn = document.getElementById('waiting-mute-btn');
          btn.innerHTML = waitMuted ? MIC_OFF_SVG : MIC_ON_SVG;
          btn.style.background = waitMuted ? '#EA4335' : '#3C4043';
        });

        // ── Camera toggle while waiting ─────────────────────────────────────
        let waitCamOff = false;
        document.getElementById('waiting-video-btn')?.addEventListener('click', () => {
          waitCamOff = !waitCamOff;
          localStream?.getVideoTracks().forEach(t => t.enabled = !waitCamOff);
          const btn = document.getElementById('waiting-video-btn');
          btn.innerHTML = waitCamOff ? CAM_OFF_SVG : CAM_ON_SVG;
          btn.style.background = waitCamOff ? '#EA4335' : '#3C4043';
          const waitVideo = document.getElementById('waiting-camera');
          if (waitVideo) waitVideo.style.opacity = waitCamOff ? '0.3' : '1';
        });

        // ── Leave button ────────────────────────────────────────────────────
        document.getElementById('waiting-leave-btn')?.addEventListener('click', async () => {
          clearInterval(waitTimerInterval);
          localStream?.getTracks().forEach(t => t.stop());
          if (roomCode) await api.post(`/rooms/${roomCode}/leave`, {}).catch(() => {});
          window.location.href = '/pages/dashboard.html';
        });

        // Store timer ref for cleanup on approval/rejection
        window._waitTimerInterval = waitTimerInterval;
      }

      if (roomData.host_id === AppState.getUser().id) {
        document.getElementById('host-record-btn').style.display = 'block';
      }
    } catch(e) { 
      showToast('Failed to join room: ' + e.message, 'error'); 
      if (e.message.includes('locked')) {
        document.body.innerHTML = '<h2 style="text-align:center;margin-top:20vh;">Room is locked by host.</h2>';
      }
      return; 
    }
  }

  // Setup socket — Feature 24: robust reconnect config
  socket = io('/conference', {
    auth: { token: AppState.getToken() },
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 10000
  });
  
  // Feature 24: Reconnect overlay
  const reconnectOverlay = document.createElement('div');
  reconnectOverlay.id = 'reconnect-overlay';
  reconnectOverlay.style.cssText = 'display:none;position:fixed;top:0;left:0;right:0;background:var(--accent-danger);color:white;text-align:center;padding:0.75rem;z-index:9999;font-weight:600;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
  reconnectOverlay.innerHTML = `⚠️ Connection Lost. Reconnecting securely... <span id="reconnect-attempt" style="margin-left:8px;opacity:0.8;"></span>`;
  document.body.appendChild(reconnectOverlay);

  socket.on('disconnect', (reason) => {
    if (reason !== 'io client disconnect') {
      reconnectOverlay.style.display = 'flex';
    }
  });
  socket.on('reconnecting', (attempt) => {
    document.getElementById('reconnect-attempt').textContent = `Attempt ${attempt}...`;
  });
  socket.on('reconnect', () => {
    reconnectOverlay.style.display = 'none';
    showToast('✅ Reconnected securely', 'success');
  });

  socket.on('connect', () => {
    reconnectOverlay.style.display = 'none';
    if (amIWaiting) {
      socket.emit('join_waiting_room', { room_code: roomCode, user_id: AppState.getUser().id, name: AppState.getUser().name });
    } else {
      if (!window._hasJoinedRoom) {
        window._hasJoinedRoom = true;
        proceedToJoin();
      } else {
        // We already joined, just re-emit join_room to restore socket room membership
        socket.emit('join_room', { room_code: roomCode, token: AppState.getToken(), user_id: AppState.getUser().id, name: AppState.getUser().name });
      }
    }
  });

  socket.on('participant_approved', () => {
    if (amIWaiting) {
      amIWaiting = false;
      clearInterval(window._waitTimerInterval);
      document.getElementById('waiting-overlay').style.display = 'none';
      showToast('✅ Host approved your entry!', 'success');
      proceedToJoin();
    }
  });

  socket.on('participant_rejected', () => {
    if (amIWaiting) {
      clearInterval(window._waitTimerInterval);
      localStream?.getTracks().forEach(t => t.stop());
      document.getElementById('waiting-overlay').innerHTML = `
        <div style="text-align:center;padding:2rem;max-width:380px;">
          <div style="font-size:3rem;margin-bottom:1rem;">🚫</div>
          <h2 style="font-family:'Syne',sans-serif;margin-bottom:0.75rem;">Entry Denied</h2>
          <p style="color:#9AA0A6;margin-bottom:1.5rem;">The host did not admit you to this session.</p>
          <button onclick="window.location.href='/pages/dashboard.html'" style="background:#8AB4F8;color:#202124;border:none;padding:0.75rem 2rem;border-radius:24px;font-size:1rem;font-weight:700;cursor:pointer;">Back to Dashboard</button>
        </div>`;
    }
  });
}


async function proceedToJoin() {

  // Reuse stream from waiting room, or acquire fresh if we went straight in
  if (!localStream || localStream.getTracks().length === 0) {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    } catch(e) {
      showToast('Camera/mic permission denied', 'error');
      localStream = new MediaStream();
    }
  }

  // Render local tile
  const localTile = document.createElement('div');
  localTile.className = 'video-tile'; localTile.id = 'tile-local';
  localTile.dataset.userId = AppState.getUser()?.id || '';
  localTile.innerHTML = `<video autoplay playsinline muted></video>
    <div class="name-label" style="display:flex;align-items:center;gap:0.5rem;">
      <span id="local-name-display">${AppState.getUser()?.name || 'You'} (You)</span>
      <button id="edit-name-btn" style="background:transparent;border:none;color:var(--accent-primary);cursor:pointer;font-size:0.8rem;padding:0;" title="Change Name">✏️</button>
    </div>`;
  localTile.querySelector('video').srcObject = localStream;
  document.getElementById('video-grid').appendChild(localTile);
  updateGridLayout();

  // Reuse existing socket (created in init), just set up the peer manager
  peerManager = new PeerManager(socket, localStream);


  // Name Change Edit logic
  document.getElementById('edit-name-btn').addEventListener('click', async () => {
    const newName = prompt("Enter your new display name:", AppState.getUser()?.name);
    if (!newName || newName.trim() === '') return;
    try {
      await api.put('/auth/profile/name', { name: newName });
      const u = AppState.getUser(); u.name = newName; AppState.setAuth(u, AppState.getToken());
      document.getElementById('local-name-display').textContent = `${newName} (You)`;
      showToast('Name updated successfully', 'success');
    } catch(e) { showToast('Failed to change name', 'error'); }
  });

  socket.on('name_changed', ({ user_id, old_name, new_name, email }) => {
    if (user_id === AppState.getUser().id) return;
    showToast(`Name changed: ${old_name} is now ${new_name} (${email})`, 'warning');
    // Also update UI if we have their tile
    document.querySelectorAll('.video-tile').forEach(tile => {
      const label = tile.querySelector('.name-label');
      if (label && label.textContent === old_name) label.textContent = new_name;
    });
    document.querySelectorAll('.participant-item').forEach(item => {
      if (item.querySelector('span:nth-child(2)').textContent.includes(old_name)) {
         item.querySelector('span:nth-child(2)').textContent = new_name;
      }
    });
  });

  socket.emit('join_room', { room_code: roomCode, token: AppState.getToken(), user_id: AppState.getUser().id, name: AppState.getUser().name });
  socket.on('user_joined', ({ user_id, name, peer_id }) => {
    participantMap[peer_id] = { name, user_id };
    peerManager.addPeer(peer_id, true, name);
    addParticipant(peer_id, name, user_id);
    showToast(`${name} joined`, 'info');
  });
  socket.on('user_left', ({ user_id, peer_id }) => {
    peerManager.removePeer(peer_id);
    document.getElementById(`p-${peer_id}`)?.remove();
    showToast('A participant left', 'info');
  });
  socket.on('receive_offer', ({ from, sdp }) => { peerManager.addPeer(from, false); peerManager.signal(from, sdp); });
  socket.on('receive_answer', ({ from, sdp }) => peerManager.signal(from, sdp));
  socket.on('receive_ice', ({ from, candidate }) => peerManager.signal(from, candidate));
  socket.on('hand_raised', ({ user_name }) => {
    showToast(`${user_name} raised their hand ✋`, 'info');
  });
  socket.on('screen_share_started', ({ user_name }) => {
    showToast(`🖥️ ${user_name} started screen sharing`, 'info');
  });
  socket.on('screen_share_stopped', ({ user_name }) => {
    showToast(`🖥️ ${user_name} stopped screen sharing`, 'info');
  });
  socket.on('chat_message', ({ sender, message, timestamp, is_announcement }) => appendChatMsg(sender, message, is_announcement));
  socket.on('private_message', ({ sender, message }) => {
    appendChatMsg(sender, `[Private] ${message}`);
    showToast(`Private message from ${sender}`, 'info');
  });
  socket.on('chat_locked', ({ is_locked }) => {
    if (AppState.getUser()?.role !== 'host') {
      const input = document.getElementById('chat-input');
      input.disabled = is_locked;
      input.placeholder = is_locked ? 'Chat is locked by host' : 'Send a message...';
      showToast(is_locked ? 'Chat locked' : 'Chat unlocked', 'info');
    }
  });

  // Live Quiz Socket Logic
  socket.on('launch_live_quiz', ({ question, options }) => {
    if (AppState.getUser()?.role === 'host') return;
    document.getElementById('pt-quiz-q').textContent = question;
    const optsDiv = document.getElementById('pt-quiz-options');
    optsDiv.innerHTML = options.map((opt, i) => `
      <label style="display:block;background:var(--bg-secondary);padding:0.75rem;border-radius:8px;cursor:pointer;">
        <input type="radio" name="pt_quiz_opt" value="${i}"> ${opt}
      </label>
    `).join('');
    document.getElementById('participant-quiz-modal').style.display = 'block';
  });

  socket.on('quiz_answer_submitted', ({ opt_index }) => {
    if (AppState.getUser()?.role === 'host') {
      quizResults[opt_index] = (quizResults[opt_index] || 0) + 1;
      quizTotalVotes++;
      renderQuizResults();
    }
  });
  socket.on('participant_list', ({ participants }) => {
    participants.forEach(p => addParticipant(p.peer_id, p.name, p.user_id));
  });

  // Remote Host Controls
  socket.on('force_mute', () => {
    if (!isMuted) document.getElementById('mute-btn').click();
    showToast('Host muted your microphone', 'warning');
  });
  socket.on('force_video_off', () => {
    if (!isVideoOff) document.getElementById('video-btn').click();
    showToast('Host disabled your camera', 'warning');
  });
  socket.on('force_leave', () => {
    showToast('You have been removed by the host', 'error');
    document.getElementById('leave-btn').click();
  });

  // Co-Host & Name Change Alerts
  socket.on('promoted_to_cohost', () => {
    showToast('🎉 You have been promoted to Co-Host!', 'success');
    // Grant co-host UI abilities
    document.getElementById('host-lock-btn').style.display = 'flex';
  });
  socket.on('cohost_promoted', ({ name }) => {
    showToast(`${name} has been promoted to Co-Host`, 'info');
  });
  socket.on('name_change_alert', ({ old_name, new_name, email, time }) => {
    const msg = `⚠️ Name Change: "${old_name}" → "${new_name}" (${email})`;
    showToast(msg, 'warning');
    appendChatMsg('🛡 System Alert', msg);
  });

  // Exam Pause / Resume
  socket.on('exam_paused', ({ message }) => {
    if (AppState.getUser()?.role !== 'host') {
      let overlay = document.getElementById('exam-pause-overlay');
      if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'exam-pause-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:1rem;';
        overlay.innerHTML = `<div style="font-size:3rem;">⏸️</div><h2 style="color:white;">${message}</h2>`;
        document.body.appendChild(overlay);
      } else {
        overlay.style.display = 'flex';
      }
    }
    if (AppState.getUser()?.role === 'host') showToast('Exam paused for all participants', 'info');
  });
  socket.on('exam_resumed', ({ message }) => {
    const overlay = document.getElementById('exam-pause-overlay');
    if (overlay) overlay.style.display = 'none';
    showToast(message, 'success');
  });

  // Whiteboard Socket Logic
  socket.on('whiteboard_toggled', ({ is_active }) => {
    const wb = document.getElementById('whiteboard');
    wb.style.display = is_active ? 'block' : 'none';
    if (is_active) initWhiteboard();
  });
  socket.on('draw_line', (data) => {
    if(wbCtx && wbCanvas) {
      const w = wbCanvas.width;
      const h = wbCanvas.height;
      drawLine(data.x0 * w, data.y0 * h, data.x1 * w, data.y1 * h, data.color, false);
    }
  });
  socket.on('clear_whiteboard', () => {
    if(wbCtx && wbCanvas) wbCtx.clearRect(0, 0, wbCanvas.width, wbCanvas.height);
  });

  socket.on('participant_video_effect', ({ user_id, effect }) => {
    const tiles = document.querySelectorAll('.video-tile');
    tiles.forEach(tile => {
      if (tile.dataset.userId == user_id || (user_id === AppState.getUser()?.id && tile.id === 'tile-local')) {
        tile.classList.remove('fx-blur', 'fx-synth', 'fx-hacker');
        if (effect !== 'none') {
          tile.classList.add(`fx-${effect}`);
        }
      }
    });
  });
}

function addParticipant(peerId, name, userId, email = '') {
  const list = document.getElementById('participants-list');
  if (document.getElementById(`p-${peerId}`)) return;
  const el = document.createElement('div');
  el.id = `p-${peerId}`; 
  el.style.cssText = 'padding:0.75rem;font-size:0.9rem;border-bottom:1px solid rgba(59,130,246,0.07);display:flex;justify-content:space-between;align-items:center;';
  
  let hostControls = '';
  if (AppState.getUser()?.role === 'host' && userId && userId !== AppState.getUser().id) {
    hostControls = `
      <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;">
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Mute" onclick="window.remoteMute('${userId}')">🔇</button>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Stop Video" onclick="window.remoteVideoOff('${userId}')">🚫</button>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Kick" onclick="window.remoteKick('${userId}')">👢</button>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Block" onclick="window.remoteBlock('${userId}', '${peerId}')">🛑</button>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Message" onclick="window.remoteMessage('${userId}')">💬</button>
        <button style="background:transparent;border:none;cursor:pointer;font-size:1.1rem;" title="Promote Co-Host" onclick="window.promoteCoHost('${userId}', '${name}')">👑</button>
      </div>
    `;
  }
  
  const emailHtml = email ? `<div style="font-size:0.72rem;color:var(--text-secondary);margin-top:2px;">${email}</div>` : '';
  el.innerHTML = `<div><div>${name}</div>${emailHtml}</div>${hostControls}`;
  list.appendChild(el);
}

function appendChatMsg(sender, message, isAnnouncement = false) {
  const box = document.getElementById('chat-messages');
  const el = document.createElement('div'); el.className = 'chat-msg';
  if (isAnnouncement) {
    el.innerHTML = `<div style="background:var(--accent-warning);color:white;padding:0.5rem;border-radius:8px;font-weight:600;margin:0.5rem 0;">📢 Announcement: ${message}</div>`;
    showToast(`📢 Announcement: ${message}`, 'warning');
  } else {
    el.innerHTML = `<div class="sender">${sender}</div><div class="bubble">${message}</div>`;
  }
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

// Controls — Feature 4: Video & Audio Participation
document.getElementById('mute-btn').addEventListener('click', () => {
  if (!localStream) return;
  isMuted = !isMuted;
  localStream.getAudioTracks().forEach(t => t.enabled = !isMuted);
  const btn = document.getElementById('mute-btn');
  btn.innerHTML = isMuted ? MIC_OFF_SVG : MIC_ON_SVG;
  btn.classList.toggle('active', isMuted);
  btn.title = isMuted ? 'Unmute Microphone' : 'Mute Microphone';
  socket?.emit('mute_status', { room_code: roomCode, muted: isMuted });
});
document.getElementById('video-btn').addEventListener('click', () => {
  if (!localStream) return;
  isVideoOff = !isVideoOff;
  localStream.getVideoTracks().forEach(t => t.enabled = !isVideoOff);
  const btn = document.getElementById('video-btn');
  btn.innerHTML = isVideoOff ? CAM_OFF_SVG : CAM_ON_SVG;
  btn.classList.toggle('active', isVideoOff);
  btn.title = isVideoOff ? 'Turn Camera On' : 'Turn Camera Off';
  // Grey out local tile when cam is off
  const localTile = document.getElementById('tile-local');
  if (localTile) localTile.style.opacity = isVideoOff ? '0.4' : '1';
  socket?.emit('video_status', { room_code: roomCode, video_off: isVideoOff });
});

document.getElementById('screen-btn').addEventListener('click', async () => {
  if (!isScreenSharing) {
    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const track = screenStream.getVideoTracks()[0];
      Object.values(peerManager?.peers || {}).forEach(peer => {
        const sender = peer._pc?.getSenders()?.find(s => s.track?.kind === 'video');
        if (sender) sender.replaceTrack(track);
      });
      track.onended = () => {
        isScreenSharing = false;
        document.getElementById('screen-btn').classList.remove('active');
        socket?.emit('screen_share_stopped', { room_code: roomCode, user_name: AppState.getUser()?.name });
      };
      isScreenSharing = true;
      document.getElementById('screen-btn').classList.add('active');
      socket?.emit('screen_share_started', { room_code: roomCode, user_name: AppState.getUser()?.name });
    } catch(e) { showToast('Screen share cancelled', 'info'); }
  }
});
document.getElementById('hand-btn').addEventListener('click', () => {
  socket?.emit('raise_hand', { room_code: roomCode, user_name: AppState.getUser().name });
  showToast('Hand raised ✋', 'info');
});
document.getElementById('leave-btn').addEventListener('click', async () => {
  if (AppState.getUser()?.role === 'host' && fullTranscript.length > 50) {
    if (confirm('Class ended. Do you want to generate an AI summary from the transcript?')) {
      try {
        const room = await api.get(`/rooms/${roomCode}`);
        await api.post('/ai/record-lecture', { room_id: room.id, transcript: fullTranscript });
        showToast('Transcript saved! Check AI Teaching Studio for summary.', 'success');
      } catch(e) { showToast('Failed to save transcript', 'error'); }
    }
  }
  socket?.emit('leave_room', { room_code: roomCode });
  if (roomCode) await api.post(`/rooms/${roomCode}/leave`, {}).catch(() => {});
  localStream?.getTracks().forEach(t => t.stop());
  window.location.href = '/pages/dashboard.html';
});
document.getElementById('toggle-panel-btn').addEventListener('click', () => {
  document.getElementById('side-panel').classList.toggle('open');
  document.getElementById('main-view').classList.toggle('panel-open');
});
document.getElementById('close-panel-btn')?.addEventListener('click', () => {
  document.getElementById('side-panel').classList.remove('open');
  document.getElementById('main-view').classList.remove('panel-open');
});
document.getElementById('send-chat-btn').addEventListener('click', () => {
  const input = document.getElementById('chat-input');
  if (!input.value.trim() || input.disabled) return;
  const isAnnounce = document.getElementById('chat-announce-toggle')?.checked || false;
  socket?.emit('chat_message', { room_code: roomCode, message: input.value, sender: AppState.getUser().name, is_announcement: isAnnounce });
  input.value = '';
});
document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('send-chat-btn').click();
});
document.getElementById('chat-lock-toggle')?.addEventListener('change', (e) => {
  socket?.emit('chat_locked', { room_code: roomCode, is_locked: e.target.checked });
});

// Panel tabs
document.querySelectorAll('.panel-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const tabName = tab.dataset.tab;
    document.getElementById('participants-panel').style.display = tabName === 'participants' ? 'block' : 'none';
    document.getElementById('chat-panel').style.display = tabName === 'chat' ? 'flex' : 'none';
    if(document.getElementById('transcript-panel')) {
      document.getElementById('transcript-panel').style.display = tabName === 'transcript' ? 'flex' : 'none';
    }
    if(document.getElementById('waiting-panel')) {
      document.getElementById('waiting-panel').style.display = tabName === 'waiting' ? 'block' : 'none';
    }
  });
});

// Host Features
if (AppState.getUser()?.role === 'host') {
  document.getElementById('host-exam-btn').style.display = 'flex';
  document.getElementById('host-record-btn').style.display = 'flex';
  document.getElementById('host-transcribe-btn').style.display = 'flex';
  document.getElementById('host-lock-btn').style.display = 'flex';
  document.getElementById('host-quiz-btn').style.display = 'flex';
  document.getElementById('chat-settings').style.display = 'flex';
  document.getElementById('tab-transcript').style.display = 'block';
  
  if (roomData?.waiting_room_enabled) {
    document.getElementById('tab-waiting').style.display = 'block';
  }
  
  if (roomData?.room_type === 'exam') {
    document.getElementById('host-pause-exam-btn').style.display = 'flex';
  }

  // Host Whiteboard Toggle
  let isWhiteboardActive = false;
  document.getElementById('host-whiteboard-btn').style.display = 'flex';
  document.getElementById('host-whiteboard-btn').addEventListener('click', () => {
    isWhiteboardActive = !isWhiteboardActive;
    socket.emit('toggle_whiteboard', { room_code: roomCode, is_active: isWhiteboardActive });
    document.getElementById('host-whiteboard-btn').classList.toggle('active', isWhiteboardActive);
  });

  // Remote actions attached to window
  window.remoteMute = (userId) => {
    socket.emit('force_mute', { target_user_id: userId });
    showToast('Sent mute request', 'info');
  };
  window.remoteVideoOff = (userId) => {
    socket.emit('force_video_off', { target_user_id: userId });
    showToast('Sent stop video request', 'info');
  };
  window.remoteKick = (userId) => {
    socket.emit('force_leave', { target_user_id: userId });
    showToast('User kicked', 'info');
  };
  window.remoteBlock = async (userId, peerId) => {
    try {
      await api.post(`/rooms/${roomData.id}/participants/${userId}/block`, {});
      window.remoteKick(userId);
      showToast('User blocked', 'success');
    } catch(e) { showToast('Error blocking user', 'error'); }
  };
  let isLocked = roomData?.is_locked || false;
  const lockBtn = document.getElementById('host-lock-btn');
  lockBtn.textContent = isLocked ? '🔒' : '🔓';
  lockBtn.addEventListener('click', async () => {
    try {
      await api.post(`/rooms/${roomData.id}/state`, { is_locked: !isLocked });
      isLocked = !isLocked;
      lockBtn.textContent = isLocked ? '🔒' : '🔓';
      showToast(isLocked ? 'Room locked' : 'Room unlocked', 'info');
    } catch(e) { showToast('Error updating lock state', 'error'); }
  });

  // Waiting Room Logic
  const waitingListEl = document.getElementById('waiting-list');
  const waitingBadge = document.getElementById('waiting-badge');
  let waitingUsers = [];

  const updateWaitingUI = () => {
    waitingBadge.textContent = waitingUsers.length;
    waitingBadge.style.display = waitingUsers.length > 0 ? 'inline-block' : 'none';
    waitingListEl.innerHTML = waitingUsers.length ? '' : '<div style="color:var(--text-secondary);">No one is waiting</div>';
    waitingUsers.forEach(u => {
      const div = document.createElement('div');
      div.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:12px;background:white;border-radius:8px;margin-bottom:8px;box-shadow:0 1px 2px rgba(0,0,0,0.05);';
      div.innerHTML = `
        <div><div style="font-weight:600;font-size:0.95rem;">${u.name}</div><div style="font-size:0.8rem;color:var(--text-secondary);">${u.email || ''}</div></div>
        <div style="display:flex;gap:8px;">
          <button style="background:var(--icon-green-bg);color:var(--accent-success);border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:600;" onclick="approveUser('${u.id}')">Admit</button>
          <button style="background:var(--icon-red-bg);color:var(--accent-danger);border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:600;" onclick="rejectUser('${u.id}')">Deny</button>
        </div>
      `;
      waitingListEl.appendChild(div);
    });
  };

  window.approveUser = async (userId) => {
    try {
      await api.post(`/rooms/${roomData.id}/participants/${userId}/status`, { status: 'approved' });
      socket.emit('approve_participant', { room_code: roomCode, user_id: userId });
      waitingUsers = waitingUsers.filter(u => u.id !== userId);
      updateWaitingUI();
    } catch(e) { showToast('Error admitting user', 'error'); }
  };

  window.rejectUser = async (userId) => {
    try {
      await api.post(`/rooms/${roomData.id}/participants/${userId}/status`, { status: 'rejected' });
      socket.emit('reject_participant', { room_code: roomCode, user_id: userId });
      waitingUsers = waitingUsers.filter(u => u.id !== userId);
      updateWaitingUI();
    } catch(e) { showToast('Error denying user', 'error'); }
  };

  const fetchWaiting = async () => {
    if (!roomData) return;
    try {
      waitingUsers = await api.get(`/rooms/${roomData.id}/waiting`);
      updateWaitingUI();
    } catch(e) {}
  };
  
  if (roomData?.waiting_room_enabled) {
    fetchWaiting();
  }

  socket?.on('participant_waiting', (user) => {
    if (!waitingUsers.find(u => u.id === user.user_id)) {
      waitingUsers.push({ id: user.user_id, name: user.name, email: '' });
      updateWaitingUI();
      showToast(`${user.name} is waiting to join`, 'info');
    }
  });

  // Exam Creation
  const examModal = document.getElementById('create-exam-modal');
  document.getElementById('host-exam-btn').addEventListener('click', () => examModal.style.display = 'flex');
  document.getElementById('cancel-create-exam').addEventListener('click', () => examModal.style.display = 'none');
  document.getElementById('confirm-create-exam').addEventListener('click', async () => {
    const title = document.getElementById('exam-title').value.trim() || 'Untitled Exam';
    const duration = parseInt(document.getElementById('exam-duration').value) || 60;
    try {
      const room = await api.get(`/rooms/${roomCode}`);
      await api.post('/exams/create', { room_id: room.id, title, duration_minutes: duration });
      showToast('Exam created successfully', 'success');
      examModal.style.display = 'none';
    } catch(e) { showToast('Error creating exam: ' + e.message, 'error'); }
  });

  // Recording
  let mediaRecorder = null;
  let recordedChunks = [];
  document.getElementById('host-record-btn').addEventListener('click', async () => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      try {
        const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) recordedChunks.push(e.data); };
        mediaRecorder.onstop = () => {
          const blob = new Blob(recordedChunks, { type: 'video/webm' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.style.display = 'none'; a.href = url; a.download = `recording_${roomCode}.webm`;
          document.body.appendChild(a); a.click();
          window.URL.revokeObjectURL(url);
          recordedChunks = [];
          document.getElementById('host-record-btn').classList.remove('active');
          stream.getTracks().forEach(t => t.stop());
        };
        mediaRecorder.start();
        document.getElementById('host-record-btn').classList.add('active');
        showToast('Recording started', 'info');
      } catch(e) { showToast('Recording cancelled', 'error'); }
    } else {
      mediaRecorder.stop();
      showToast('Recording stopped, downloading...', 'info');
    }
  });

  // Live Transcription
  let recognition = null;
  let fullTranscript = '';
  document.getElementById('host-transcribe-btn').addEventListener('click', () => {
    if (!recognition) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return showToast('Speech recognition not supported in this browser', 'error');
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      
      recognition.onresult = (e) => {
        let interim = '';
        let final = '';
        for (let i = e.resultIndex; i < e.results.length; ++i) {
          if (e.results[i].isFinal) final += e.results[i][0].transcript;
          else interim += e.results[i][0].transcript;
        }
        if (final) {
          fullTranscript += final + ' ';
          document.getElementById('live-transcript').textContent = fullTranscript;
        }
      };
      recognition.start();
      document.getElementById('host-transcribe-btn').classList.add('active');
      document.getElementById('live-transcript').textContent = 'Listening...';
      document.getElementById('summarize-btn').style.display = 'none';
      showToast('Live transcription started', 'info');
    } else {
      recognition.stop();
      recognition = null;
      document.getElementById('host-transcribe-btn').classList.remove('active');
      document.getElementById('summarize-btn').style.display = 'block';
      showToast('Live transcription stopped', 'info');
    }
  });

  document.getElementById('summarize-btn').addEventListener('click', async () => {
    if (!fullTranscript.trim()) return showToast('No transcript to summarize', 'error');
    const summarizeBtn = document.getElementById('summarize-btn');
    summarizeBtn.textContent = 'Summarizing...';
    summarizeBtn.disabled = true;
    try {
      const room = await api.get(`/rooms/${roomCode}`);
      const lectureData = await api.post('/ai/record-lecture', {
        room_id: room.id,
        transcript: fullTranscript
      });
      const summaryData = await api.post('/ai/summarize', { lecture_id: lectureData.lecture_id });
      document.getElementById('summary-result').textContent = summaryData.summary;
    } catch(e) {
      showToast('Failed to summarize: ' + e.message, 'error');
    } finally {
      summarizeBtn.textContent = 'Generate Summary';
      summarizeBtn.disabled = false;
    }
  });
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'm') document.getElementById('mute-btn').click();
  if (e.key === 'v') document.getElementById('video-btn').click();
  if (e.key === 'h') document.getElementById('hand-btn').click();
});

// Whiteboard Logic
let wbCanvas, wbCtx;
let drawing = false;
let current = { color: 'black' };

function initWhiteboard() {
  if (wbCanvas) return;
  wbCanvas = document.getElementById('whiteboard');
  wbCtx = wbCanvas.getContext('2d');
  
  const resize = () => {
    wbCanvas.width = wbCanvas.offsetWidth;
    wbCanvas.height = wbCanvas.offsetHeight;
  };
  window.addEventListener('resize', resize);
  resize();

  wbCanvas.addEventListener('mousedown', onMouseDown, false);
  wbCanvas.addEventListener('mouseup', onMouseUp, false);
  wbCanvas.addEventListener('mouseout', onMouseUp, false);
  wbCanvas.addEventListener('mousemove', throttle(onMouseMove, 10), false);
  
  // Touch support
  wbCanvas.addEventListener('touchstart', onMouseDown, false);
  wbCanvas.addEventListener('touchend', onMouseUp, false);
  wbCanvas.addEventListener('touchcancel', onMouseUp, false);
  wbCanvas.addEventListener('touchmove', throttle(onMouseMove, 10), false);
}

function drawLine(x0, y0, x1, y1, color, emit) {
  wbCtx.beginPath();
  wbCtx.moveTo(x0, y0);
  wbCtx.lineTo(x1, y1);
  wbCtx.strokeStyle = color;
  wbCtx.lineWidth = 2;
  wbCtx.stroke();
  wbCtx.closePath();

  if (!emit) return;
  const w = wbCanvas.width;
  const h = wbCanvas.height;
  socket.emit('draw_line', {
    room_code: roomCode,
    x0: x0 / w, y0: y0 / h,
    x1: x1 / w, y1: y1 / h,
    color: color
  });
}

function onMouseDown(e) {
  drawing = true;
  current.x = getX(e); current.y = getY(e);
}
function onMouseUp(e) {
  if (!drawing) return;
  drawing = false;
  drawLine(current.x, current.y, getX(e), getY(e), current.color, true);
}
function onMouseMove(e) {
  if (!drawing) return;
  drawLine(current.x, current.y, getX(e), getY(e), current.color, true);
  current.x = getX(e); current.y = getY(e);
}

function getX(e) { return e.clientX || e.touches[0].clientX; }
function getY(e) { return (e.clientY || e.touches[0].clientY) - 80; } // offset for header if any, might need boundingrect

function throttle(callback, delay) {
  let previousCall = new Date().getTime();
  return function() {
    const time = new Date().getTime();
    if ((time - previousCall) >= delay) { previousCall = time; callback.apply(null, arguments); }
  };
}

let mediaRecorder = null;
let recordedChunks = [];

document.getElementById('host-record-btn')?.addEventListener('click', async () => {
  const btn = document.getElementById('host-record-btn');
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    btn.classList.remove('active');
    btn.style.background = '#e8f0fe';
    btn.style.color = '#1a73e8';
    btn.textContent = '⏺️';
    showToast('Recording stopped. Saving file...', 'info');
    return;
  }
  
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
    mediaRecorder = new MediaRecorder(stream);
    recordedChunks = [];
    
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: 'video/webm' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `Lecture_Recording_${roomCode}_${new Date().toISOString().replace(/:/g, '-')}.webm`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
      stream.getTracks().forEach(t => t.stop());
    };
    
    mediaRecorder.start();
    btn.classList.add('active');
    btn.style.background = '#fce8e6';
    btn.style.color = '#d93025';
    btn.textContent = '⏹️';
    showToast('Recording started', 'success');
  } catch(e) { showToast('Recording cancelled', 'error'); }
});

init();

// Live Quiz & Private Message Logic
let quizResults = {};
let quizTotalVotes = 0;
let quizOptions = [];

window.remoteMessage = (userId) => {
  const msg = prompt('Enter private message:');
  if (msg && msg.trim()) {
    socket?.emit('private_message', { target_user_id: userId, sender: AppState.getUser().name, message: msg.trim() });
    appendChatMsg('You', `[Private to ${userId.slice(0,5)}] ${msg.trim()}`);
  }
};

document.getElementById('host-quiz-btn')?.addEventListener('click', () => {
  document.getElementById('create-quiz-modal').style.display = 'flex';
});
document.getElementById('cancel-quiz-btn')?.addEventListener('click', () => {
  document.getElementById('create-quiz-modal').style.display = 'none';
});
document.getElementById('add-quiz-opt')?.addEventListener('click', () => {
  const div = document.createElement('input');
  div.type = 'text'; div.className = 'quiz-opt';
  div.style.cssText = 'width:100%;border-radius:8px;padding:0.5rem;margin-bottom:0.5rem;';
  div.placeholder = `Option ${String.fromCharCode(65 + document.querySelectorAll('.quiz-opt').length)}`;
  document.getElementById('quiz-options').appendChild(div);
});
document.getElementById('launch-quiz-btn')?.addEventListener('click', () => {
  const q = document.getElementById('quiz-question').value.trim();
  const opts = Array.from(document.querySelectorAll('.quiz-opt')).map(i => i.value.trim()).filter(Boolean);
  if (!q || opts.length < 2) { showToast('Enter a question and at least 2 options', 'error'); return; }
  
  quizResults = {}; quizTotalVotes = 0; quizOptions = opts;
  socket?.emit('launch_live_quiz', { room_code: roomCode, question: q, options: opts });
  document.getElementById('create-quiz-modal').style.display = 'none';
  document.getElementById('host-quiz-monitor').style.display = 'block';
  renderQuizResults();
});

document.getElementById('close-quiz-monitor')?.addEventListener('click', () => {
  document.getElementById('host-quiz-monitor').style.display = 'none';
});

function renderQuizResults() {
  document.getElementById('quiz-total-votes').textContent = `${quizTotalVotes} votes`;
  const container = document.getElementById('quiz-results-bars');
  container.innerHTML = quizOptions.map((opt, i) => {
    const votes = quizResults[i] || 0;
    const pct = quizTotalVotes === 0 ? 0 : Math.round((votes / quizTotalVotes) * 100);
    return `
      <div style="margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:2px;">
          <span>${opt}</span><span>${pct}% (${votes})</span>
        </div>
        <div style="width:100%;height:6px;background:var(--bg-primary);border-radius:4px;overflow:hidden;">
          <div style="height:100%;width:${pct}%;background:var(--accent-primary);transition:width 0.3s;"></div>
        </div>
      </div>
    `;
  }).join('');
}

document.getElementById('submit-quiz-answer-btn')?.addEventListener('click', () => {
  const selected = document.querySelector('input[name="pt_quiz_opt"]:checked');
  if (!selected) { showToast('Select an answer', 'error'); return; }
  socket?.emit('submit_quiz_answer', { room_code: roomCode, host_id: roomData.host_id, opt_index: selected.value });
  document.getElementById('participant-quiz-modal').style.display = 'none';
  showToast('Answer submitted!', 'success');
});

// ─── Co-Host Promotion ───────────────────────────────────────────────
window.promoteCoHost = (userId, name) => {
  if (!confirm(`Promote ${name} to Co-Host?`)) return;
  socket?.emit('promote_cohost', {
    room_code: roomCode,
    target_user_id: userId,
    name: name
  });
  showToast(`${name} promoted to Co-Host`, 'success');
};

// ─── Settings Modal & Background Glow ────────────────────────────────
document.getElementById('settings-btn')?.addEventListener('click', () => {
  const modal = document.getElementById('settings-modal');
  if (modal) {
    modal.style.display = 'flex';
    const input = document.getElementById('settings-name-input');
    if (input) input.value = AppState.getUser()?.name || 'Guest';
  }
});

document.getElementById('settings-save-name-btn')?.addEventListener('click', async () => {
  const input = document.getElementById('settings-name-input');
  const newName = input?.value?.trim();
  if (!newName) return;
  const user = AppState.getUser();
  const oldName = user.name || 'Guest';
  if (newName === oldName) return;

  try {
    await api.put('/auth/profile/name', { name: newName });
    user.name = newName;
    AppState.setAuth(user, AppState.getToken());
    
    // Update local video name labels
    const localName = document.getElementById('local-name-display');
    if (localName) localName.textContent = `${newName} (You)`;
    const selfLabel = document.getElementById('self-name-label');
    if (selfLabel) selfLabel.textContent = newName;

    // Notify others
    socket?.emit('name_changed', {
      room_code: roomCode,
      user_id: user.id,
      old_name: oldName,
      new_name: newName,
      email: user.email,
      host_id: roomData?.host_id
    });
    
    showToast(`Name updated to "${newName}"`, 'success');
  } catch(e) {
    showToast('Failed to update name', 'error');
  }
});

// Background FX toggles
document.querySelectorAll('.bg-fx-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.bg-fx-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    const fx = btn.getAttribute('data-fx');
    const localTile = document.getElementById('tile-local');
    
    if (localTile) {
      localTile.classList.remove('fx-blur', 'fx-synth', 'fx-hacker');
      if (fx !== 'none') {
        localTile.classList.add(`fx-${fx}`);
      }
    }
    
    socket?.emit('video_effect', {
      room_code: roomCode,
      user_id: AppState.getUser().id,
      effect: fx
    });
  });
});

// ─── Exam Pause / Resume (Host only) ─────────────────────────────────
let examPaused = false;
document.getElementById('host-pause-exam-btn')?.addEventListener('click', () => {
  const btn = document.getElementById('host-pause-exam-btn');
  if (!examPaused) {
    socket?.emit('pause_exam', { room_code: roomCode });
    btn.textContent = '▶️ Resume Exam';
    btn.title = 'Resume Exam';
    examPaused = true;
  } else {
    socket?.emit('resume_exam', { room_code: roomCode });
    btn.textContent = '⏸️ Pause Exam';
    btn.title = 'Pause Exam';
    examPaused = false;
  }
});
