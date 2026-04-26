import { reactive } from 'vue'

const state = reactive({
  visible: false,
  message: '',
  type: 'info', // success, error, warning, info
  timeout: null,

  // Confirm dialog
  confirmVisible: false,
  confirmTitle: '',
  confirmMessage: '',
  confirmResolve: null,

  // Prompt dialog
  promptVisible: false,
  promptTitle: '',
  promptMessage: '',
  promptValue: '',
  promptResolve: null,
})

let toastId = 0

export function useToast() {
  const show = (message, type = 'info', duration = 3500) => {
    if (state.timeout) clearTimeout(state.timeout)
    state.message = message
    state.type = type
    state.visible = true
    state.key = ++toastId
    state.timeout = setTimeout(() => {
      state.visible = false
    }, duration)
  }

  const success = (msg) => show(msg, 'success')
  const error = (msg) => show(msg, 'error')
  const warning = (msg) => show(msg, 'warning')
  const info = (msg) => show(msg, 'info')

  const dismiss = () => {
    if (state.timeout) clearTimeout(state.timeout)
    state.visible = false
  }

  // Confirm dialog: returns Promise<boolean>
  const confirm = (message, title = '确认') => new Promise((resolve) => {
    state.confirmTitle = title
    state.confirmMessage = message
    state.confirmVisible = true
    state.confirmResolve = resolve
  })

  // Called by ConfirmDialog when user clicks confirm/cancel
  const confirmAction = () => {
    state.confirmVisible = false
    state.confirmResolve?.(true)
  }
  const cancel = () => {
    state.confirmVisible = false
    state.confirmResolve?.(false)
  }

  // Prompt dialog: returns Promise<string | null>
  const prompt = (message, title = '输入', defaultValue = '') => new Promise((resolve) => {
    state.promptTitle = title
    state.promptMessage = message
    state.promptValue = defaultValue
    state.promptVisible = true
    state.promptResolve = resolve
  })

  const promptConfirm = () => {
    state.promptVisible = false
    state.promptResolve?.(state.promptValue)
  }

  const promptCancel = () => {
    state.promptVisible = false
    state.promptResolve?.(null)
  }

  return {
    state, show, success, error, warning, info, dismiss,
    confirm, confirmAction, cancel,
    prompt, promptConfirm, promptCancel,
  }
}
