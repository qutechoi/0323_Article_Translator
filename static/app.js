'use strict';

// ── Provider / Model definitions ─────────────────────────────────────────────
const PROVIDERS = {
  anthropic: {
    label: 'Anthropic (Claude)',
    models: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-6'],
    customModel: false,
    requireKey: true,
    showBaseUrl: false,
  },
  openai: {
    label: 'OpenAI (GPT)',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'],
    customModel: false,
    requireKey: true,
    showBaseUrl: false,
  },
  google: {
    label: 'Google (Gemini)',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
    customModel: false,
    requireKey: true,
    showBaseUrl: false,
  },
  lmstudio: {
    label: 'LM Studio (로컬)',
    models: [],
    customModel: true,
    requireKey: false,
    showBaseUrl: true,
  },
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const providerSel = $('provider');
const modelSel = $('model');
const modelCustom = $('model-custom');
const apiKeyInput = $('api-key');
const baseUrlInput = $('base-url');
const apiKeyField = $('api-key-field');
const baseUrlField = $('base-url-field');
const dropArea = $('drop-area');
const fileInput = $('file-input');
const selectedFileName = $('selected-file-name');
const translateBtn = $('translate-btn');

const uploadZone = $('upload-zone');
const progressZone = $('progress-zone');
const resultZone = $('result-zone');

const progressBar = $('progress-bar');
const progressPercent = $('progress-percent');
const progressLabel = $('progress-label');
const progressStatus = $('progress-status');

const panelsEl = $('panels');
const pdfViewer = $('pdf-viewer');
const bodyTranslated = $('body-translated');
const translatedPdfViewer = $('translated-pdf-viewer');
const headerTranslated = $('header-translated');

const copyBtn = $('copy-btn');
const saveBtn = $('save-btn');
const newBtn = $('new-btn');
const toast = $('toast');

// ── State ────────────────────────────────────────────────────────────────────
let selectedFile = null;
let currentJobId = null;
let sse = null;
let sections = [];   // { index, is_heading, original_text, translated_text }

// ── Settings persistence ──────────────────────────────────────────────────────
function saveSettings() {
  const cfg = {
    provider: providerSel.value,
    model: modelSel.value,
    modelCustom: modelCustom.value,
    apiKey: apiKeyInput.value,
    baseUrl: baseUrlInput.value,
  };
  localStorage.setItem('at_settings', JSON.stringify(cfg));
}

function loadSettings() {
  try {
    const raw = localStorage.getItem('at_settings');
    if (!raw) return;
    const cfg = JSON.parse(raw);
    if (cfg.provider && PROVIDERS[cfg.provider]) {
      providerSel.value = cfg.provider;
    }
    updateProviderUI();
    if (cfg.model) modelSel.value = cfg.model;
    if (cfg.modelCustom) modelCustom.value = cfg.modelCustom;
    if (cfg.apiKey) apiKeyInput.value = cfg.apiKey;
    if (cfg.baseUrl) baseUrlInput.value = cfg.baseUrl;
  } catch (_) {}
}

// ── Provider UI ───────────────────────────────────────────────────────────────
function updateProviderUI() {
  const prov = PROVIDERS[providerSel.value];

  // Rebuild model dropdown
  modelSel.innerHTML = '';
  if (prov.models.length) {
    prov.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      modelSel.appendChild(opt);
    });
    modelSel.style.display = '';
    modelCustom.style.display = prov.customModel ? '' : 'none';
  } else {
    modelSel.style.display = 'none';
    modelCustom.style.display = '';
    modelCustom.placeholder = '로드된 모델명 입력 (예: mistral-7b)';
  }

  apiKeyField.style.display = prov.requireKey ? '' : 'none';
  baseUrlField.style.display = prov.showBaseUrl ? '' : 'none';
}

providerSel.addEventListener('change', () => { updateProviderUI(); saveSettings(); });
modelSel.addEventListener('change', saveSettings);
modelCustom.addEventListener('input', saveSettings);
apiKeyInput.addEventListener('input', saveSettings);
baseUrlInput.addEventListener('input', saveSettings);

// ── File selection ────────────────────────────────────────────────────────────
dropArea.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => handleFile(fileInput.files[0]));

dropArea.addEventListener('dragover', e => { e.preventDefault(); dropArea.classList.add('drag-over'); });
dropArea.addEventListener('dragleave', () => dropArea.classList.remove('drag-over'));
dropArea.addEventListener('drop', e => {
  e.preventDefault();
  dropArea.classList.remove('drag-over');
  handleFile(e.dataTransfer.files[0]);
});

function handleFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('PDF 파일만 업로드할 수 있습니다.');
    return;
  }
  selectedFile = file;
  selectedFileName.textContent = `선택된 파일: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  translateBtn.disabled = false;
}

// ── Translate ─────────────────────────────────────────────────────────────────
translateBtn.addEventListener('click', startTranslation);

async function startTranslation() {
  if (!selectedFile) return;

  const prov = providerSel.value;
  const provCfg = PROVIDERS[prov];
  const model = provCfg.customModel
    ? (modelCustom.value.trim() || modelSel.value)
    : modelSel.value;
  const apiKey = apiKeyInput.value.trim();
  const baseUrl = baseUrlInput.value.trim() || 'http://localhost:1234/v1';

  if (provCfg.requireKey && !apiKey) {
    showToast('API 키를 입력해주세요.');
    return;
  }
  if (provCfg.customModel && !model) {
    showToast('모델명을 입력해주세요.');
    return;
  }

  // Show progress
  sections = [];
  showZone('progress');
  setProgress(0, '파일 업로드 중...');

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('provider', prov);
  fd.append('model', model);
  fd.append('api_key', apiKey);
  fd.append('base_url', baseUrl);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '업로드 실패');
    }
    const { job_id } = await res.json();
    currentJobId = job_id;
    pdfViewer.src = `/api/pdf/${job_id}`;
    listenProgress(job_id);
  } catch (e) {
    showZone('upload');
    showToast(e.message);
  }
}

// ── SSE progress ──────────────────────────────────────────────────────────────
function listenProgress(jobId) {
  if (sse) sse.close();
  sse = new EventSource(`/api/progress/${jobId}`);

  sse.addEventListener('status', e => {
    const d = JSON.parse(e.data);
    if (d.status === 'parsing') setProgress(0, 'PDF 파싱 중...');
    if (d.status === 'translating') setProgress(0, `번역 중... (0 / ${d.total} 청크)`);
  });

  sse.addEventListener('chunk_done', e => {
    const d = JSON.parse(e.data);
    setProgress(d.percent, `번역 중... (${d.chunk} / ${d.total} 청크)`);

    // Merge incoming sections
    d.sections.forEach(s => {
      const existing = sections.find(x => x.index === s.index);
      if (existing) {
        existing.translated_text = s.translated_text;
      } else {
        sections.push(s);
        sections.sort((a, b) => a.index - b.index);
      }
    });
    renderPanels();

    // Switch to result zone early (once first chunk arrives)
    if (resultZone.style.display !== 'flex') showZone('result');
  });

  sse.addEventListener('complete', () => {
    sse.close();
    setProgress(100, '번역 완료! PDF 생성 중...');
    fetchFullResult();
    showTranslatedLoading();
    pollForTranslatedPdf(jobId);
  });

  sse.addEventListener('error', e => {
    sse.close();
    let msg = '번역 중 오류가 발생했습니다.';
    try { msg = JSON.parse(e.data).message; } catch (_) {}
    showZone('upload');
    showToast(msg);
  });

  sse.onerror = () => {};
}

// ── Poll for translated PDF ──────────────────────────────────────────────────
async function pollForTranslatedPdf(jobId) {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 500));
    try {
      const res = await fetch(`/api/result/${jobId}`);
      if (!res.ok) continue;
      const data = await res.json();
      if (data.pdf_ready) {
        showTranslatedPdf(jobId);
        return;
      }
      if (data.pdf_error) {
        fallbackToText(`PDF 생성 실패: ${data.pdf_error}`);
        return;
      }
    } catch (_) {}
  }
  fallbackToText('PDF 생성 시간이 초과되었습니다.');
}

function fallbackToText(msg) {
  const loading = $('translated-loading');
  if (loading) loading.style.display = 'none';
  bodyTranslated.style.display = '';
  showToast(msg);
}

async function fetchFullResult() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/api/result/${currentJobId}`);
    const data = await res.json();
    sections = data.sections;
    sections.sort((a, b) => a.index - b.index);
    renderPanels();
    showZone('result');
  } catch (_) {}
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderPanels() {
  bodyTranslated.innerHTML = '';

  sections.forEach(sec => {
    const tranEl = makeSectionEl(sec);
    bodyTranslated.appendChild(tranEl);
  });
}

function makeSectionEl(sec) {
  const div = document.createElement('div');
  div.className = 'section-block' + (sec.is_heading ? ' is-heading' : '');
  div.dataset.index = sec.index;

  const p = document.createElement('p');
  if (sec.translated_text) {
    p.className = 'section-text';
    p.textContent = sec.translated_text;
  } else {
    p.className = 'section-placeholder';
    p.textContent = '번역 중...';
  }
  div.appendChild(p);
  return div;
}

// ── Tabs ───────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    panelsEl.className = 'panels';
    if (tab === 'original') panelsEl.classList.add('show-original');
    if (tab === 'translated') panelsEl.classList.add('show-translated');
  });
});

// ── Copy / Save ───────────────────────────────────────────────────────────────
copyBtn.addEventListener('click', () => {
  const txt = sections
    .map(s => s.translated_text || '')
    .filter(Boolean)
    .join('\n\n');
  navigator.clipboard.writeText(txt).then(() => showToast('복사되었습니다.', 'success'));
});

saveBtn.addEventListener('click', () => {
  const txt = sections.map(s => {
    const prefix = s.is_heading ? '=== ' : '';
    const suffix = s.is_heading ? ' ===' : '';
    return prefix + (s.translated_text || '') + suffix;
  }).join('\n\n');

  const blob = new Blob([txt], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'translation.txt';
  a.click();
  URL.revokeObjectURL(url);
});

newBtn.addEventListener('click', async () => {
  if (sse) sse.close();
  if (currentJobId) {
    fetch(`/api/job/${currentJobId}`, { method: 'DELETE' }).catch(() => {});
  }
  selectedFile = null;
  fileInput.value = '';
  selectedFileName.textContent = '';
  translateBtn.disabled = true;
  sections = [];
  currentJobId = null;
  pdfViewer.src = '';
  translatedPdfViewer.src = '';
  translatedPdfViewer.style.display = 'none';
  bodyTranslated.style.display = '';
  bodyTranslated.innerHTML = '';
  headerTranslated.textContent = '번역문 (한국어)';
  // 탭을 기본(나란히 보기)으로 리셋
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-tab="side"]').classList.add('active');
  panelsEl.className = 'panels';
  showZone('upload');
});

// ── Translated PDF helpers ─────────────────────────────────────────────────────
function showTranslatedLoading() {
  bodyTranslated.style.display = 'none';
  translatedPdfViewer.style.display = 'none';

  // 로딩 스피너를 패널 안에 표시
  let loading = $('translated-loading');
  if (!loading) {
    loading = document.createElement('div');
    loading.id = 'translated-loading';
    loading.className = 'pdf-generating';
    loading.innerHTML = '<div class="spinner"></div><span>번역 PDF 생성 중...</span>';
    $('panel-translated').appendChild(loading);
  }
  loading.style.display = 'flex';
}

function showTranslatedPdf(jobId) {
  const loading = $('translated-loading');
  if (loading) loading.style.display = 'none';

  bodyTranslated.style.display = 'none';
  translatedPdfViewer.src = `/api/translated-pdf/${jobId}`;
  translatedPdfViewer.style.display = 'block';
  headerTranslated.textContent = '번역문 PDF (한국어)';
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setProgress(pct, label) {
  progressBar.style.width = pct + '%';
  progressPercent.textContent = pct + '%';
  progressLabel.textContent = label;
}

function showZone(zone) {
  uploadZone.style.display = zone === 'upload' ? 'flex' : 'none';
  progressZone.style.display = zone === 'progress' ? 'flex' : 'none';
  resultZone.style.display = zone === 'result' ? 'flex' : 'none';
}

let toastTimer = null;
function showToast(msg, type = 'error') {
  toast.textContent = msg;
  toast.style.background = type === 'success' ? 'var(--success)' : 'var(--error)';
  toast.style.display = 'block';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 3500);
}

// ── Init ──────────────────────────────────────────────────────────────────────
updateProviderUI();
loadSettings();
showZone('upload');
