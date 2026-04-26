<template>
  <Teleport to="body">
    <div v-if="state.promptVisible" class="modal-overlay">
      <div class="modal confirm-modal">
        <div class="modal-header">
          <h3>{{ state.promptTitle }}</h3>
          <button class="btn btn-default" @click="promptCancel" title="取消">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <p class="confirm-message">{{ state.promptMessage }}</p>
        <input v-model="state.promptValue" class="prompt-input" @keyup.enter="promptConfirm" placeholder="请输入..." />
        <div class="modal-actions">
          <button class="btn btn-primary" @click="promptConfirm">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            确定
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import { useToast } from '../composables/useToast.js'

export default {
  name: 'PromptDialog',
  setup() {
    const { state, promptConfirm, promptCancel } = useToast()
    return { state, promptConfirm, promptCancel }
  },
}
</script>

<style scoped>
.confirm-modal { width: 400px; }
.confirm-message {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 8px 0 0;
  line-height: 1.6;
}
.prompt-input {
  width: 100%;
  padding: 9px 12px;
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  background: #f9fafb;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.prompt-input:focus {
  border-color: var(--accent);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(108,92,231,0.1);
}
.confirm-modal .modal-actions {
  justify-content: flex-end;
  margin-top: 24px;
}
</style>
