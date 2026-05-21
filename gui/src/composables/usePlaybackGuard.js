import { ref } from 'vue'

const currentEl = ref(null)

export function usePlaybackGuard() {
  const play = (el) => {
    if (!el) return
    if (currentEl.value && currentEl.value !== el) {
      currentEl.value.pause()
    }
    currentEl.value = el
    el.play()
  }

  const pause = (el) => {
    if (!el) return
    if (currentEl.value === el) {
      currentEl.value = null
    }
    el.pause()
  }

  return { play, pause }
}
