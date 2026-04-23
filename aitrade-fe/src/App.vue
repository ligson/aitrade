<template>
  <div class="app-route-progress" :class="{ 'is-visible': routeLoading.visible, 'is-failed': routeLoading.failed }" :style="progressStyle">
    <span class="app-route-progress-glow" :style="glowStyle" />
  </div>
  <RouterView />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { useRouteLoading } from '@/stores/routeLoading'

const routeLoading = useRouteLoading()
const progressStyle = computed(() => ({
  transform: `scaleX(${Math.max(routeLoading.progress.value / 100, 0.01)})`,
}))
const glowStyle = computed(() => ({
  left: routeLoading.shimmerOffset.value,
}))
</script>
