import { AppState } from '../core/state.js';
import { api } from '../core/api.js';
import { showToast } from '../components/toast.js';

if (!AppState.getToken() || AppState.getUser()?.role !== 'host') {
  window.location.href = '/pages/login.html';
}

document.getElementById('logout-btn').addEventListener('click', () => {
  AppState.logout();
  window.location.href = '/pages/login.html';
});

const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
  uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    handleFileUpload(e.target.files[0]);
  }
});

async function handleFileUpload(file) {
  showToast('Uploading file...', 'info');
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const res = await fetch('http://127.0.0.1:5000/api/files/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${AppState.getToken()}`
      },
      body: formData
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Upload failed');
    
    showToast('File uploaded successfully!', 'success');
    loadFiles();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

async function loadFiles() {
  const grid = document.getElementById('files-grid');
  try {
    const files = await api.get('/files/list');
    if (files.length === 0) {
      grid.innerHTML = '<div style="color:var(--text-secondary);grid-column:1/-1;text-align:center;">No files found in storage.</div>';
      return;
    }
    
    grid.innerHTML = files.map(f => {
      const ext = f.filename.split('.').pop().toLowerCase();
      let icon = '📁';
      let typeLabel = 'File';
      if (['pdf'].includes(ext)) { icon = '📄'; typeLabel = 'PDF Document'; }
      else if (['mp4', 'webm', 'mov'].includes(ext)) { icon = '🎥'; typeLabel = 'Video Recording'; }
      else if (['jpg', 'png', 'jpeg'].includes(ext)) { icon = '🖼️'; typeLabel = 'Image'; }
      else if (['json', 'txt', 'csv'].includes(ext)) { icon = '📝'; typeLabel = 'Text/Data'; }
      
      const canPreview = ['pdf', 'jpg', 'png', 'jpeg', 'mp4', 'webm'].includes(ext);

      return `
      <div class="file-card" style="display:flex;flex-direction:column;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:1.25rem;transition:transform 0.2s,box-shadow 0.2s;">
        <div style="display:flex;align-items:flex-start;gap:1rem;margin-bottom:1rem;">
          <div class="file-icon" style="font-size:2.5rem;background:rgba(138,180,248,0.1);padding:0.75rem;border-radius:12px;display:flex;align-items:center;justify-content:center;">${icon}</div>
          <div class="file-details" style="flex:1;min-width:0;">
            <h4 title="${f.filename}" style="margin:0 0 0.25rem 0;font-size:1rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${f.filename}</h4>
            <div style="font-size:0.75rem;color:var(--accent-primary);font-weight:600;margin-bottom:0.25rem;">${typeLabel}</div>
            <p style="margin:0;font-size:0.8rem;color:var(--text-secondary);">${formatBytes(f.file_size)} • ${new Date(f.uploaded_at).toLocaleDateString()}</p>
          </div>
        </div>
        <div class="file-actions" style="display:flex;gap:0.75rem;margin-top:auto;">
          ${canPreview ? `<button class="btn-primary" style="flex:1;padding:0.5rem;font-size:0.85rem;" onclick="window.previewFile('${f.id}', '${ext}')">👀 Preview</button>` : ''}
          <button class="btn-outline" style="flex:1;padding:0.5rem;font-size:0.85rem;" onclick="window.downloadFile('${f.id}', '${f.filename}')">📥 Download</button>
        </div>
      </div>
    `}).join('');
  } catch (e) {
    grid.innerHTML = '<div style="color:var(--accent-danger);">Failed to load files</div>';
  }
}

window.previewFile = async (id, ext) => {
  showToast('Opening preview...', 'info');
  try {
    const res = await fetch(`http://127.0.0.1:5000/api/files/download/${id}`, {
      headers: { 'Authorization': `Bearer ${AppState.getToken()}` }
    });
    if (!res.ok) throw new Error('Preview failed');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
  } catch (e) {
    showToast(e.message, 'error');
  }
};

window.downloadFile = async (id, filename) => {
  showToast('Preparing download...', 'info');
  try {
    const res = await fetch(`http://127.0.0.1:5000/api/files/download/${id}`, {
      headers: { 'Authorization': `Bearer ${AppState.getToken()}` }
    });
    if (!res.ok) throw new Error('Download failed');
    
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (e) {
    showToast(e.message, 'error');
  }
};

loadFiles();
