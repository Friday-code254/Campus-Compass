const uploadForm = document.querySelector('#upload-form');
const fileInput = document.querySelector('#file-input');
const chooseFile = document.querySelector('#choose-file');
const uploadStatus = document.querySelector('#upload-status');
const documentList = document.querySelector('#document-list');
const documentCount = document.querySelector('#document-count');
const emptyDocuments = document.querySelector('#empty-documents');
const chatForm = document.querySelector('#chat-form');
const questionInput = document.querySelector('#question-input');
const sendButton = document.querySelector('#send-button');
const conversation = document.querySelector('#conversation');
const welcome = document.querySelector('#welcome');
const uploadCard = document.querySelector('.upload-card');

function make(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) { /* Keep the status message. */ }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function readableSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function refreshDocuments() {
  try {
    const documents = await request('/api/documents');
    documentList.replaceChildren();
    documentCount.textContent = String(documents.length);
    emptyDocuments.hidden = documents.length > 0;
    for (const document of documents) {
      const item = make('li', 'document-item');
      const ext = document.filename.split('.').pop().toUpperCase().slice(0, 3);
      item.append(make('span', 'file-icon', ext));
      const copy = make('span', 'document-copy');
      copy.append(make('span', 'document-name', document.filename));
      copy.append(make('span', 'document-meta', `${document.chunk_count} passages`));
      item.append(copy);
      const remove = make('button', 'delete-document', '×');
      remove.type = 'button';
      remove.title = `Remove ${document.filename}`;
      remove.setAttribute('aria-label', `Remove ${document.filename}`);
      remove.addEventListener('click', async () => {
        remove.disabled = true;
        try {
          await request(`/api/documents/${encodeURIComponent(document.id)}`, { method: 'DELETE' });
          await refreshDocuments();
          uploadStatus.textContent = 'Document removed.';
        } catch (error) {
          uploadStatus.textContent = error.message;
          remove.disabled = false;
        }
      });
      item.append(remove);
      documentList.append(item);
    }
  } catch (error) {
    emptyDocuments.hidden = false;
    emptyDocuments.querySelector('p').textContent = 'Could not load documents.';
  }
}

async function upload(file) {
  if (!file) return;
  uploadStatus.textContent = `Adding ${file.name}…`;
  const body = new FormData();
  body.append('file', file);
  try {
    const result = await request('/api/documents', { method: 'POST', body });
    await refreshDocuments();
    uploadStatus.textContent = result.duplicate ? 'That file is already in your library.' : `Added ${result.filename}.`;
  } catch (error) {
    uploadStatus.textContent = error.message;
  } finally {
    uploadForm.reset();
  }
}

chooseFile.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => upload(fileInput.files[0]));
uploadForm.addEventListener('submit', (event) => event.preventDefault());

for (const eventName of ['dragenter', 'dragover']) {
  uploadCard.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadCard.classList.add('dragover');
  });
}
for (const eventName of ['dragleave', 'drop']) {
  uploadCard.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadCard.classList.remove('dragover');
  });
}
uploadCard.addEventListener('drop', (event) => upload(event.dataTransfer.files[0]));

function appendMessage(role, text, result = null) {
  welcome.hidden = true;
  const message = make('article', `message ${role}`);
  message.append(make('div', 'avatar', role === 'assistant' ? 'C' : 'Y'));
  const body = make('div', 'message-body');
  body.append(make('div', 'message-label', role === 'assistant' ? 'CAMPUS COMPASS' : 'YOU'));
  body.append(make('p', 'message-text', text));
  if (result?.mode) {
    const modeLabels = {
      generated: 'Generated from retrieved passages.',
      retrieval_preview: 'Retrieval preview · no LLM endpoint configured.',
      generation_unavailable: 'Retrieved evidence is shown below.',
      abstained: 'No sufficiently relevant passage was found.',
      greeting: 'Ready to answer questions about your uploaded documents.',
    };
    body.append(make('p', 'mode-note', modeLabels[result.mode] || ''));
  }
  if (result?.sources?.length) {
    const sources = make('div', 'sources');
    for (const source of result.sources) {
      const card = make('details', 'source-card');
      const summary = make('summary');
      summary.append(make('span', 'source-label', `[${source.label}]`));
      const location = source.page_number ? ` · page ${source.page_number}` : '';
      const section = source.section ? ` · ${source.section}` : '';
      summary.append(make('span', 'source-name', `${source.filename}${location}${section}`));
      summary.append(make('span', 'source-score', `match ${Number(source.score).toFixed(2)}`));
      card.append(summary);
      card.append(make('p', 'source-text', source.text));
      sources.append(card);
    }
    body.append(sources);
  }
  message.append(body);
  conversation.append(message);
  conversation.scrollTop = conversation.scrollHeight;
}

async function ask(question) {
  const clean = question.trim();
  if (!clean) return;
  appendMessage('user', clean);
  questionInput.value = '';
  sendButton.disabled = true;
  sendButton.textContent = '…';
  try {
    const result = await request('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: clean }),
    });
    appendMessage('assistant', result.answer, result);
  } catch (error) {
    appendMessage('assistant', `I couldn't complete that request: ${error.message}`);
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = '↑';
    questionInput.focus();
  }
}

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  ask(questionInput.value);
});
questionInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
questionInput.addEventListener('input', () => {
  questionInput.style.height = 'auto';
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 110)}px`;
});
document.querySelectorAll('.suggestion').forEach((button) => {
  button.addEventListener('click', () => ask(button.textContent));
});

refreshDocuments();

