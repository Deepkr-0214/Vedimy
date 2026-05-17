import { AppState } from '../core/state.js';
import { api } from '../core/api.js';
import { showToast } from '../components/toast.js';

if (!AppState.getToken()) window.location.href = '/pages/login.html';

let currentLectureId = null;
let currentAiLectureId = null;
let selectedCount = 5, selectedType = 'mcq', selectedDiff = 'easy';
let generatedQuestions = [];

// Word count
const transcriptArea = document.getElementById('transcript-area');
const wordCountEl = document.getElementById('word-count');
transcriptArea.addEventListener('input', () => {
  wordCountEl.textContent = transcriptArea.value.trim().split(/\s+/).filter(Boolean).length + ' words';
});

// Save & analyze
document.getElementById('save-lecture-btn').addEventListener('click', async () => {
  const transcript = transcriptArea.value.trim();
  if (transcript.length < 30) { showToast('Please enter a longer transcript', 'error'); return; }
  document.getElementById('save-lecture-btn').textContent = '⏳ Saving...';
  try {
    const res = await api.post('/ai/record-lecture', {
      title: `Lecture ${new Date().toLocaleDateString()}`,
      transcript, source: 'manual'
    });
    currentLectureId = res.lecture_id;
    showToast('Lecture saved!', 'success');
    await generateSummary();
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  } finally {
    document.getElementById('save-lecture-btn').textContent = '💾 Save & Analyze';
  }
});

// PDF Upload
const dropZone = document.getElementById('drop-zone');
const pdfInput = document.getElementById('pdf-input');
const processBtn = document.getElementById('process-pdf-btn');
let pdfFile = null;

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  pdfFile = e.dataTransfer.files[0];
  if (pdfFile?.name.endsWith('.pdf')) {
    processBtn.disabled = false;
    document.getElementById('pdf-filename').textContent = '📎 ' + pdfFile.name;
  }
});
pdfInput.addEventListener('change', () => {
  pdfFile = pdfInput.files[0];
  if (pdfFile) { processBtn.disabled = false; document.getElementById('pdf-filename').textContent = '📎 ' + pdfFile.name; }
});
processBtn.addEventListener('click', async () => {
  if (!pdfFile) return;
  processBtn.textContent = '⏳ Extracting...';
  try {
    const formData = new FormData();
    formData.append('pdf', pdfFile);
    const res = await fetch('/api/ai/upload-pdf', {
      method: 'POST',
      headers: { Authorization: `Bearer ${AppState.getToken()}` },
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    transcriptArea.value = data.transcript;
    wordCountEl.textContent = data.word_count + ' words';
    showToast('PDF extracted! Review text then Save & Analyze', 'success');
  } catch(e) { showToast('PDF error: ' + e.message, 'error'); }
  finally { processBtn.textContent = '⚙️ Extract Text'; }
});

async function generateSummary() {
  const section = document.getElementById('summary-section');
  section.style.display = 'block';
  document.getElementById('summary-loading').style.display = 'block';
  document.getElementById('summary-content').innerHTML = '';

  try {
    const res = await api.post('/ai/summarize', { lecture_id: currentLectureId });
    currentAiLectureId = res.ai_lecture_id;
    document.getElementById('summary-content').innerHTML = `<p style="line-height:1.75;">${res.summary}</p>`;
    document.getElementById('key-points-list').innerHTML =
      '<h3 style="font-size:1rem;margin-bottom:0.75rem;">Key Points</h3><ul style="margin-left:1.25rem;line-height:1.8;">' +
      res.key_points.map(p => `<li>${p}</li>`).join('') + '</ul>';
    document.getElementById('topics-chips').innerHTML =
      '<h3 style="font-size:1rem;margin-bottom:0.5rem;">Important Topics</h3>' +
      res.important_topics.map(t => `<span class="chip">${t}</span>`).join('');
    document.getElementById('translation-section').style.display = 'block';
    document.getElementById('exam-section').style.display = 'block';
    await loadLanguages();
    showToast('AI summary generated!', 'success');
  } catch(e) { showToast('Summarization failed: ' + e.message, 'error'); }
  finally { document.getElementById('summary-loading').style.display = 'none'; }
}

async function loadLanguages() {
  try {
    const langs = await api.get('/ai/languages', false);
    const pills = document.getElementById('language-pills');
    pills.innerHTML = Object.entries(langs).map(([code, name]) =>
      `<button class="pill lang-pill" data-lang="${code}">${name}</button>`
    ).join('');
    pills.querySelectorAll('.lang-pill').forEach(btn =>
      btn.addEventListener('click', () => translateTo(btn.dataset.lang))
    );
  } catch(e) {}
}

async function translateTo(lang) {
  if (!currentAiLectureId) return;
  const el = document.getElementById('translated-content');
  el.style.display = 'block'; el.innerHTML = '<div class="skeleton-loader" style="height:80px;"></div>';
  try {
    const res = await api.post('/ai/translate', { ai_lecture_id: currentAiLectureId, target_language: lang });
    el.innerHTML = `
      <p style="margin-bottom:0.75rem;line-height:1.7;">${res.translated_summary}</p>
      <ul style="margin-left:1.25rem;line-height:1.8;">${res.translated_key_points.map(p => `<li>${p}</li>`).join('')}</ul>
    `;
  } catch(e) { el.innerHTML = '<p style="color:var(--accent-danger);">Translation failed</p>'; }
}

// Pill groups
['count', 'type', 'diff'].forEach(group => {
  document.querySelectorAll(`#${group}-pills .pill`).forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll(`#${group}-pills .pill`).forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (group === 'count') selectedCount = parseInt(btn.dataset.val);
      if (group === 'type') selectedType = btn.dataset.val;
      if (group === 'diff') selectedDiff = btn.dataset.val;
    });
  });
});

document.getElementById('generate-btn').addEventListener('click', async () => {
  if (!currentLectureId) { showToast('Save a lecture first', 'error'); return; }
  document.getElementById('generate-btn').textContent = '⏳ Generating...';
  try {
    const res = await api.post('/ai/generate-questions', {
      lecture_id: currentLectureId, count: selectedCount,
      type: selectedType, difficulty: selectedDiff
    });
    generatedQuestions = res.questions;
    renderQuestions(res.questions);
    document.getElementById('export-row').style.display = 'flex';
    showToast(`${res.questions.length} questions generated!`, 'success');
  } catch(e) { showToast('Generation failed: ' + e.message, 'error'); }
  finally { document.getElementById('generate-btn').textContent = '✨ Generate Questions'; }
});

function renderQuestions(questions) {
  document.getElementById('questions-preview').innerHTML = questions.map((q, i) => `
    <div class="question-card">
      <p><strong>Q${i+1}.</strong> ${q.question}</p>
      ${q.type === 'mcq' ? `
        <ul>${q.options.map(o => `<li class="${o.startsWith('A)') ? 'correct' : ''}">${o}</li>`).join('')}</ul>
        <details><summary>Explanation</summary><p style="margin-top:0.5rem;font-size:0.875rem;">${q.explanation}</p></details>
      ` : `
        <details><summary>Model Answer</summary><p style="margin-top:0.5rem;">${q.model_answer}</p></details>
      `}
    </div>
  `).join('');
}

document.getElementById('export-btn').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(generatedQuestions, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'vedimy-questions.json'; a.click();
  URL.revokeObjectURL(url);
});

async function loadUpcomingExams() {
  try {
    const exams = await api.get('/exams/upcoming');
    const select = document.getElementById('exam-select');
    select.innerHTML = '<option value="">-- Select Exam --</option>';
    exams.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.id;
      opt.textContent = `${e.title} (${e.duration_minutes}m)`;
      select.appendChild(opt);
    });
  } catch(e) {}
}

document.getElementById('attach-exam-btn').addEventListener('click', async () => {
  const examId = document.getElementById('exam-select').value;
  if (!examId) { showToast('Please select an exam', 'error'); return; }
  if (generatedQuestions.length === 0) { showToast('No questions generated', 'error'); return; }
  try {
    await api.put(`/exams/${examId}/questions`, { questions: generatedQuestions });
    showToast('Questions attached to exam!', 'success');
  } catch(e) { showToast('Failed to attach: ' + e.message, 'error'); }
});

loadUpcomingExams();
