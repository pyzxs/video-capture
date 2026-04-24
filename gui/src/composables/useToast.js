import { reactive } from 'vue'

const state = reactive({
  visible: false,
  message: '',
  type: 'info', // success, error, warning, info
  timeout: null,
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

  return { state, show, success, error, warning, info, dismiss }
}
