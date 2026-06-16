<template>
  <div class="container">
    <h1>Upload a PDF</h1>

    <div class="form">
      <label>
        Company ID
        <input type="number" v-model.number="companyId" min="1" required />
      </label>

      <label class="file-input-label">
        <span class="file-input-button">
          {{ file ? file.name : 'Choose PDF File' }}
        </span>
        <input type="file" accept="application/pdf" @change="onFileChange" class="file-input-hidden" />
      </label>

      <p v-if="loading" class="uploading">⏳ Uploading {{ file?.name }}...</p>
    </div>

    <p v-if="message" :class="{ success: success, error: !success }">{{ message }}</p>

    <div class="help">
      <p>Backend endpoint: {{ apiBase }}/docs/upload</p>
    </div>

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
          <span v-if="docStatus.status === 'ready'">✅ Ready! You can now ask questions below.</span>
          <span v-if="docStatus.status === 'error'">❌ Processing failed. Please try uploading again.</span>
        </div>
      </div>
    </div>

    <hr class="divider" />

    <div class="chat-section">
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import axios from 'axios';

const apiBase = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';

const companyId = ref<number>(1);
const file = ref<File | null>(null);
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

async function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  const selectedFile = target.files && target.files[0] ? target.files[0] : null;
  
  if (!selectedFile) return;
  
  file.value = selectedFile;
  
  // Auto-upload immediately
  loading.value = true;
  message.value = '';
  success.value = false;
  
  try {
    const form = new FormData();
    form.append('company_id', String(companyId.value));
    form.append('file', selectedFile);

    const res = await axios.post(`${apiBase}/docs/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    success.value = true;
    message.value = `✅ Uploaded! document_id=${res.data.document_id}`;
    uploadedDocId.value = res.data.document_id;
    // Start polling for status updates
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
      company_id: companyId.value,
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
  max-width: 760px;
  margin: 40px auto;
  padding: 24px;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji";
}

h1 { margin-bottom: 16px; }

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

input[type="number"], input[type="text"] {
  padding: 8px;
}

button {
  padding: 10px 14px;
  cursor: pointer;
}

.file-input-label {
  cursor: pointer;
}

.file-input-hidden {
  display: none;
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
  margin-top: 24px;
}

.chat-section h2 {
  margin-bottom: 16px;
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
</style>