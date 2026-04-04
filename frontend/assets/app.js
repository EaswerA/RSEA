const uploadForm = document.getElementById('upload-form');
const pdfInput = document.getElementById('pdf-input');
const fileLabel = document.getElementById('file-label');
const uploadStatus = document.getElementById('upload-status');
const refreshBtn = document.getElementById('refresh-btn');
const summary = document.getElementById('summary');
const extractionsBody = document.getElementById('extractions-body');
const logsBody = document.getElementById('logs-body');

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function outputToDownloadLink(outputFile) {
  if (!outputFile) return '';
  const filename = outputFile.split('/').pop();
  if (!filename) return escapeHtml(outputFile);
  return `<a class="file-link" href="/files/${encodeURIComponent(filename)}" target="_blank" rel="noreferrer">${escapeHtml(filename)}</a>`;
}

function setStatus(message, type = '') {
  uploadStatus.textContent = message;
  uploadStatus.className = `status ${type}`.trim();
}

async function loadRecords() {
  const response = await fetch('/records/?limit=25');
  if (!response.ok) {
    throw new Error(`Failed to load records: ${response.status}`);
  }

  const data = await response.json();
  const extractions = data.extractions || [];
  const logs = data.processing_logs || [];

  summary.textContent = `Showing ${extractions.length} extraction rows and ${logs.length} processing logs from MongoDB.`;

  extractionsBody.innerHTML = extractions
    .map((item) => {
      const confidence = item.confidence == null ? '-' : Number(item.confidence).toFixed(2);
      return `
        <tr>
          <td>${escapeHtml(item.source_filename)}</td>
          <td>${escapeHtml(item.component)}</td>
          <td>${escapeHtml(item.item_type)}</td>
          <td>${escapeHtml(item.value)} ${escapeHtml(item.unit)}</td>
          <td>${escapeHtml(confidence)}</td>
          <td>${outputToDownloadLink(item.output_file)}</td>
        </tr>
      `;
    })
    .join('');

  logsBody.innerHTML = logs
    .map((item) => {
      return `
        <tr>
          <td>${escapeHtml(item.source_filename)}</td>
          <td>${escapeHtml(item.status)}</td>
          <td>${escapeHtml(item.items_extracted)}</td>
          <td>${escapeHtml(item.created_at)}</td>
          <td>${outputToDownloadLink(item.output_file)}</td>
        </tr>
      `;
    })
    .join('');
}

pdfInput.addEventListener('change', () => {
  const file = pdfInput.files?.[0];
  fileLabel.textContent = file ? file.name : 'Choose a PDF file';
});

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = pdfInput.files?.[0];

  if (!file) {
    setStatus('Please select a PDF file first.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  setStatus('Uploading and extracting...');

  try {
    const response = await fetch('/upload/', {
      method: 'POST',
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.detail || 'Upload failed.';
      throw new Error(detail);
    }

    setStatus(`Done. Extracted ${payload.items_extracted} items.`, 'ok');
    await loadRecords();
  } catch (error) {
    setStatus(error.message || 'Unexpected error.', 'error');
  }
});

refreshBtn.addEventListener('click', async () => {
  try {
    await loadRecords();
    setStatus('Records refreshed.', 'ok');
  } catch (error) {
    setStatus(error.message || 'Could not refresh records.', 'error');
  }
});

loadRecords().catch((error) => {
  setStatus(error.message || 'Could not load initial records.', 'error');
});
