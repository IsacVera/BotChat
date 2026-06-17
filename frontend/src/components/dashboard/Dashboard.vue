<template>
  <div class="container">
    <h1>My heart</h1>
    <div class="form">
      <p class="fixed-company">Using company 1</p>

      <p v-if="loading" class="uploading">⏳ Importing the server-side PDF...</p>
    </div>

    <p v-if="message && !success" class="error">{{ message }}</p>

    <div v-if="docStatus" class="doc-status">
      <div class="status-info">
        <p><strong>Filename:</strong> {{ docStatus.filename }}</p>
        <p><strong>Status:</strong> <span :class="'status-' + docStatus.status">{{ docStatus.status.toUpperCase() }}</span></p>
        <p v-if="docStatus.page_count"><strong>Pages:</strong> {{ docStatus.page_count }}</p>
        <div v-if="docStatus.error_message && docStatus.error_message.includes('embedding_error')" class="warning-message">
          <strong>⚠️ Warning:</strong> Vector embeddings failed. Search will use keyword-only mode (may be less accurate).
          <details style="margin-top: 8px;">
            <summary style="cursor: pointer; color: #666;">Technical details</summary>
            <p style="margin-top: 8px; font-size: 12px; color: #666;">{{ docStatus.error_message }}</p>
          </details>
        </div>
        <p v-else-if="docStatus.error_message" class="error"><strong>Error:</strong> {{ docStatus.error_message }}</p>
        <div class="help-text">
          <span v-if="docStatus.status === 'uploaded'">⏳ Waiting for processing...</span>
          <span v-if="docStatus.status === 'processing'">⚙️ Processing document...</span>
          <span v-if="docStatus.status === 'ready'">✅ You can now ask questions below.</span>
          <span v-if="docStatus.status === 'error'">❌ Processing failed. Please try uploading again.</span>
        </div>
      </div>
    </div>

    <hr class="divider" />

    <div class="workspace">
      <section class="pdf-panel">
        <div class="panel-header">
          <h2>PDF</h2>
          <p v-if="docStatus?.page_count" class="panel-meta">{{ docStatus.page_count }} pages</p>
        </div>

        <div v-if="pdfUrl && docStatus?.status === 'ready'" class="pdf-frame-wrap">
          <iframe
            :src="pdfViewerUrl"
            title="Document PDF preview"
            class="pdf-frame"
          />
        </div>

        <p v-if="pdfUrl && docStatus?.status === 'ready'" class="pdf-link-row">
          <a :href="pdfUrl" target="_blank" rel="noreferrer">Open PDF in a new tab</a>
        </p>

        <div v-else class="pdf-placeholder">
          <p v-if="docStatus?.status === 'processing' || docStatus?.status === 'uploaded'">The PDF will appear here as soon as processing finishes.</p>
          <p v-else-if="docStatus?.status === 'error'">The PDF preview is unavailable because document processing failed.</p>
          <p v-else>Importing the PDF.</p>
        </div>
      </section>

      <section class="chat-section">
        <h2>💬 Ask the Chatbot</h2>
        <form @submit.prevent="onAsk" class="form chat-form">
          <label>
            <input 
              type="text" 
              v-model="question" 
              placeholder="Ask about your uploaded PDF..." 
              class="question-input"
              :disabled="!docStatus || docStatus.status !== 'ready'"
            />
          </label>
          <button 
            type="submit" 
            :disabled="asking || !question || !docStatus || docStatus.status !== 'ready'"
            class="ask-button"
          >
            {{ asking ? 'Asking…' : 'Ask' }}
          </button>
        </form>

        <div v-if="askError" class="error error-box">{{ askError }}</div>

        <div v-if="answer" class="result">
          <h3>Answer</h3>
          <pre>{{ answer }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';

const apiBase = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';
const companyId = 1;

const loading = ref(false);
const message = ref('');
const success = ref(false);

const question = ref('');
const asking = ref(false);
const answer = ref('');
const askError = ref('');

const uploadedDocId = ref<number | null>(null);
const docStatus = ref<any>(null);
const checkingStatus = ref(false);
let statusCheckInterval: any = null;

const pdfUrl = computed(() => {
  if (!docStatus.value?.storage_path || docStatus.value.status !== 'ready') {
    return '';
  }
  return `${apiBase}/media/${docStatus.value.storage_path}`;
});

const pdfViewerUrl = computed(() => {
  if (!pdfUrl.value) {
    return '';
  }
  return `${pdfUrl.value}#toolbar=1&navpanes=0&view=FitH`;
});

onMounted(() => {
  void loadConfiguredPdf();
});

async function loadConfiguredPdf() {
  loading.value = true;
  message.value = '';
  success.value = false;
  
  try {
    const res = await axios.post(`${apiBase}/docs/load-default`, {
      company_id: companyId,
    });

    success.value = true;
    message.value = '';
    uploadedDocId.value = res.data.document_id;
    startStatusPolling();
  } catch (err: any) {
    console.error(err);
    success.value = false;
    if (err.response?.data?.error) {
      message.value = `Error: ${err.response.data.error}`;
    } else {
      message.value = 'Upload failed. See console for details.';
    }
  } finally {
    loading.value = false;
  }
}

async function checkDocStatus() {
  if (!uploadedDocId.value) return;
  checkingStatus.value = true;
  try {
    const res = await axios.get(`${apiBase}/docs/${uploadedDocId.value}`);
    docStatus.value = res.data;
    
    // If status is ready or error, stop polling
    if (docStatus.value.status === 'ready' || docStatus.value.status === 'error') {
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
      }
    }
  } catch (err: any) {
    console.error(err);
    message.value = 'Failed to check document status';
    success.value = false;
  } finally {
    checkingStatus.value = false;
  }
}

function startStatusPolling() {
  // Clear any existing interval
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval);
  }
  // Check immediately
  checkDocStatus();
  // Then poll every 2 seconds
  statusCheckInterval = setInterval(() => {
    checkDocStatus();
  }, 2000);
}

async function onAsk() {
  askError.value = '';
  answer.value = '';
  if (!question.value) return;
  try {
    asking.value = true;
    const res = await axios.post(`${apiBase}/chat/ask`, {
      company_id: companyId,
      question: question.value
    });
    if (!res.data.answer) {
      answer.value = 'Your question is not related to the terms of service.';
      return;
    }

    answer.value = (res.data.answer.answer || 'I do not have a response right now.')
      .replace(/\s*\[Snippet\s+\d+\]/g, '');
  } catch (err: any) {
    console.error(err);
    askError.value = err.response?.data?.error || 'Chat request failed';
  } finally {
    asking.value = false;
  }
}
</script>

<style scoped>
.container {
  max-width: 1320px;
  margin: 40px auto;
  padding: 24px;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji";
}

h1 { margin-bottom: 16px; }

.fixed-company {
  color: #555;
  font-size: 14px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

input[type="text"] {
  padding: 8px;
}

button {
  padding: 10px 14px;
  cursor: pointer;
}

.file-input-button {
  display: inline-block;
  padding: 10px 14px;
  background: #2196f3;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.file-input-button:hover {
  background: #1976d2;
}

.uploading {
  color: #2196f3;
  font-weight: 500;
  margin-top: 8px;
}

.success { color: #0a7c2f; }
.error { color: #b00020; }

.help { margin-top: 16px; color: #666; font-size: 14px; }

.divider { margin: 32px 0; }

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
  gap: 24px;
  align-items: start;
}

.panel-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-header h2,
.chat-section h2 {
  margin: 0;
}

.panel-meta {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.pdf-panel,
.chat-section {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.pdf-frame-wrap {
  border: 1px solid #d8dee8;
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
}

.pdf-frame {
  display: block;
  width: 100%;
  height: 78vh;
  min-height: 720px;
  border: 0;
}

.pdf-link-row {
  margin: 10px 0 0;
  font-size: 14px;
}

.pdf-link-row a {
  color: #2563eb;
  text-decoration: none;
}

.pdf-link-row a:hover {
  text-decoration: underline;
}

.pdf-placeholder {
  min-height: 420px;
  display: grid;
  place-items: center;
  padding: 24px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  color: #475569;
  text-align: center;
}

.result pre {
  background: #f7f7f7;
  padding: 12px;
  overflow-x: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.doc-status {
  margin: 20px 0;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.doc-status h3 {
  margin-bottom: 12px;
}

.status-info {
  margin-top: 12px;
  padding: 12px;
  background: white;
  border-radius: 4px;
}

.status-info p {
  margin: 8px 0;
}

.status-uploaded { color: #ff9800; font-weight: bold; }
.status-processing { color: #2196f3; font-weight: bold; }
.status-ready { color: #4caf50; font-weight: bold; }
.status-error { color: #f44336; font-weight: bold; }

.help-text {
  margin-top: 12px;
  padding: 8px;
  background: #e3f2fd;
  border-radius: 4px;
  font-size: 14px;
}

.chat-section {
  position: sticky;
  top: 24px;
}

.chat-form {
  display: flex;
  flex-direction: row;
  gap: 8px;
  align-items: flex-end;
}

.chat-form label {
  flex: 1;
}

.question-input {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  border: 2px solid #ddd;
  border-radius: 4px;
  transition: border-color 0.2s;
}

.question-input:focus {
  outline: none;
  border-color: #2196f3;
}

.question-input:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.ask-button {
  padding: 12px 24px;
  background: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.ask-button:hover:not(:disabled) {
  background: #45a049;
}

.ask-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.error-box {
  margin-top: 12px;
  padding: 12px;
  background: #ffebee;
  border-left: 4px solid #f44336;
  border-radius: 4px;
}

.warning-message {
  margin-top: 8px;
  padding: 12px;
  background: #fff8e1;
  border-left: 4px solid #ffa726;
  border-radius: 4px;
  font-size: 14px;
  color: #f57c00;
}

.warning-message details {
  margin-top: 8px;
}

.warning-message summary {
  cursor: pointer;
  color: #666;
  font-size: 12px;
}

@media (max-width: 960px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .chat-section {
    position: static;
  }

  .pdf-frame {
    height: 65vh;
    min-height: 520px;
  }
}
</style>