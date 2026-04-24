<template>
  <div class="app-breadcrumb">
    <a-breadcrumb>
      <a-breadcrumb-item v-for="(item, index) in items" :key="`${item.title}-${index}`">
        <span :class="index === items.length - 1 ? 'app-breadcrumb-current' : 'app-breadcrumb-parent'">{{ item.title }}</span>
      </a-breadcrumb-item>
    </a-breadcrumb>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const items = computed(() => {
  const breadcrumb = route.meta.breadcrumb
  if (Array.isArray(breadcrumb) && breadcrumb.length > 0) {
    return breadcrumb.map((item) => ({ title: String(item) }))
  }
  return route.matched
    .filter((record) => typeof record.meta.title === 'string' && record.meta.title)
    .map((record) => ({
      title: String(record.meta.title),
    }))
})
</script>

<style scoped>
.app-breadcrumb {
  display: flex;
  align-items: center;
  min-height: 40px;
  padding: 0 4px;
}

.app-breadcrumb :deep(.ant-breadcrumb) {
  font-size: 14px;
}

.app-breadcrumb-current {
  color: #111827;
  font-weight: 600;
}
</style>
