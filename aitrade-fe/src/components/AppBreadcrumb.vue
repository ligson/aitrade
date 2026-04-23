<template>
  <div class="app-breadcrumb">
    <a-breadcrumb>
      <a-breadcrumb-item v-for="(item, index) in items" :key="item.path">
        <RouterLink v-if="index < items.length - 1" :to="item.path">{{ item.title }}</RouterLink>
        <span v-else class="app-breadcrumb-current">{{ item.title }}</span>
      </a-breadcrumb-item>
    </a-breadcrumb>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const items = computed(() =>
  route.matched
    .filter((record) => typeof record.meta.title === 'string' && record.meta.title)
    .map((record) => ({
      path: record.path.startsWith('/') ? record.path : `/${record.path}`,
      title: String(record.meta.title),
    })),
)
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
