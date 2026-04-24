<template>
  <Teleport to="body">
    <transition name="toast-slide">
      <div v-if="state.visible" class="toast-wrapper" :class="'toast-' + state.type" @click="dismiss">
        <span class="toast-icon">{{ iconMap[state.type] }}</span>
        <span class="toast-text">{{ state.message }}</span>
        <button class="toast-close">&times;</button>
      </div>
    </transition>
  </Teleport>
</template>

<script>
import { useToast } from '../composables/useToast.js'

export default {
  name: 'ToastMessage',
  setup() {
    const { state, dismiss } = useToast()
    const iconMap = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ',
    }
    return { state, dismiss, iconMap }
  },
}
</script>

<style scoped>
.toast-wrapper {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 8px 30px rgba(0,0,0,0.15);
  cursor: pointer;
  min-width: 280px;
  max-width: 500px;
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.2);
}

.toast-icon {
  font-size: 14px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-weight: 700;
}

.toast-text { flex: 1; line-height: 1.4; }

.toast-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  opacity: 0.5;
  padding: 0;
  line-height: 1;
  flex-shrink: 0;
  color: inherit;
}
.toast-close:hover { opacity: 1; }

/* Types */
.toast-success {
  background: rgba(16,185,129,0.12);
  color: #059669;
  border: 1px solid rgba(16,185,129,0.2);
}
.toast-success .toast-icon { background: #10b981; color: #fff; }

.toast-error {
  background: rgba(239,68,68,0.1);
  color: #dc2626;
  border: 1px solid rgba(239,68,68,0.18);
}
.toast-error .toast-icon { background: #ef4444; color: #fff; }

.toast-warning {
  background: rgba(251,191,36,0.12);
  color: #d97706;
  border: 1px solid rgba(251,191,36,0.2);
}
.toast-warning .toast-icon { background: #f59e0b; color: #fff; }

.toast-info {
  background: rgba(108,92,231,0.1);
  color: #6c5ce7;
  border: 1px solid rgba(108,92,231,0.18);
}
.toast-info .toast-icon { background: #6c5ce7; color: #fff; }

/* Animation */
.toast-slide-enter-active { animation: toast-in 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-slide-leave-active { animation: toast-out 0.2s ease-in forwards; }

@keyframes toast-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-16px) scale(0.95); }
  to { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
}
@keyframes toast-out {
  from { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
  to { opacity: 0; transform: translateX(-50%) translateY(-12px) scale(0.95); }
}
</style>
