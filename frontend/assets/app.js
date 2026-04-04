const uploadForm = document.getElementById('upload-form');
const pdfInput = document.getElementById('pdf-input');
const fileLabel = document.getElementById('file-label');
const uploadStatus = document.getElementById('upload-status');
const refreshBtn = document.getElementById('refresh-btn');
const summary = document.getElementById('summary');
const extractionsBody = document.getElementById('extractions-body');
const logsBody = document.getElementById('logs-body');
const authForm = document.getElementById('auth-form');
const usernameInput = document.getElementById('username-input');
const passwordInput = document.getElementById('password-input');
const loginBtn = document.getElementById('login-btn');
const registerBtn = document.getElementById('register-btn');
const logoutBtn = document.getElementById('logout-btn');
const authSummary = document.getElementById('auth-summary');

const AUTH_TOKEN_KEY = 'rsea-auth-token';
const AUTH_USER_KEY = 'rsea-auth-user';

let authToken = localStorage.getItem(AUTH_TOKEN_KEY) || '';
let authUser = localStorage.getItem(AUTH_USER_KEY) || '';

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
  const filename = String(outputFile);
  if (!authToken) return escapeHtml(filename);
  const href = `/files/${encodeURIComponent(filename)}?token=${encodeURIComponent(authToken)}`;
  return `<a class="file-link" href="${href}" target="_blank" rel="noreferrer">${escapeHtml(filename)}</a>`;
}

function setStatus(message, type = '') {
  uploadStatus.textContent = message;
  uploadStatus.className = `status ${type}`.trim();
}

function clearRecordTables() {
  extractionsBody.innerHTML = '';
  logsBody.innerHTML = '';
  summary.textContent = 'Sign in to see your records.';
}

function setAuthState(token, username) {
  authToken = token || '';
  authUser = username || '';

  if (authToken) {
    localStorage.setItem(AUTH_TOKEN_KEY, authToken);
    localStorage.setItem(AUTH_USER_KEY, authUser);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  }

  const isLoggedIn = Boolean(authToken);
  authSummary.textContent = isLoggedIn ? `Signed in as ${authUser}.` : 'Not signed in.';

  uploadForm.querySelectorAll('input, button').forEach((el) => {
    el.disabled = !isLoggedIn;
  });
  refreshBtn.disabled = !isLoggedIn;
  logoutBtn.disabled = !isLoggedIn;
}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (authToken) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    setAuthState('', '');
    clearRecordTables();
    setStatus('Session expired. Please log in again.', 'error');
    throw new Error('Authentication required.');
  }

  return response;
}

async function loadRecords() {
  if (!authToken) {
    clearRecordTables();
    return;
  }

  const response = await apiFetch('/records/?limit=25');
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

async function login() {
  const username = usernameInput.value.trim().toLowerCase();
  const password = passwordInput.value;

  if (!username || !password) {
    setStatus('Enter username and password first.', 'error');
    return;
  }

  const response = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || 'Login failed.');
  }

  setAuthState(payload.token, payload.username);
  passwordInput.value = '';
  setStatus('Logged in.', 'ok');
  await loadRecords();
}

async function register() {
  const username = usernameInput.value.trim().toLowerCase();
  const password = passwordInput.value;

  if (!username || !password) {
    setStatus('Enter username and password first.', 'error');
    return;
  }

  const response = await fetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || 'Registration failed.');
  }

  setStatus('Account created. You can now log in.', 'ok');
}

loginBtn.addEventListener('click', async () => {
  try {
    await login();
  } catch (error) {
    setStatus(error.message || 'Login failed.', 'error');
  }
});

registerBtn.addEventListener('click', async () => {
  try {
    await register();
  } catch (error) {
    setStatus(error.message || 'Registration failed.', 'error');
  }
});

logoutBtn.addEventListener('click', () => {
  setAuthState('', '');
  clearRecordTables();
  setStatus('Logged out.', 'ok');
});

authForm.addEventListener('submit', (event) => {
  event.preventDefault();
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
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
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

setAuthState(authToken, authUser);

if (authToken) {
  apiFetch('/auth/me')
    .then(async (response) => {
      if (!response.ok) {
        throw new Error('Session invalid.');
      }
      const payload = await response.json();
      setAuthState(authToken, payload.username || authUser);
      return loadRecords();
    })
    .catch((error) => {
      setAuthState('', '');
      clearRecordTables();
      setStatus(error.message || 'Please log in.', 'error');
    });
} else {
  clearRecordTables();
}
