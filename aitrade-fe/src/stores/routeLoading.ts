import { computed, ref } from 'vue'

const visible = ref(false)
const progress = ref(0)
const failed = ref(false)

let timer: number | null = null
let hideTimer: number | null = null

function clearProgressTimer() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function clearHideTimer() {
  if (hideTimer !== null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
}

function reset() {
  clearProgressTimer()
  clearHideTimer()
  visible.value = false
  failed.value = false
  progress.value = 0
}

function tick() {
  const distance = 96 - progress.value
  const step = progress.value < 40 ? 8 : progress.value < 72 ? 4.5 : 1.6
  progress.value = Math.min(progress.value + Math.max(distance * 0.08, step), 96)
}

function start() {
  clearHideTimer()
  failed.value = false
  visible.value = true
  if (progress.value < 10) {
    progress.value = 10
  }
  if (progress.value < 22) {
    progress.value = 22
  }
  if (timer === null) {
    timer = window.setInterval(tick, 140)
  }
}

function finish() {
  clearProgressTimer()
  failed.value = false
  visible.value = true
  progress.value = 100
  clearHideTimer()
  hideTimer = window.setTimeout(() => {
    visible.value = false
    progress.value = 0
    hideTimer = null
  }, 260)
}

function fail() {
  clearProgressTimer()
  failed.value = true
  visible.value = true
  progress.value = 100
  clearHideTimer()
  hideTimer = window.setTimeout(() => {
    failed.value = false
    visible.value = false
    progress.value = 0
    hideTimer = null
  }, 360)
}

const shimmerOffset = computed(() => `${Math.min(progress.value + 12, 100)}%`)

export function useRouteLoading() {
  return {
    visible,
    progress,
    failed,
    shimmerOffset,
    start,
    finish,
    fail,
    reset,
  }
}
