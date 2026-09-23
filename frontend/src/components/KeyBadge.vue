<script setup lang="ts">
// Плашка с буквой варианта; win — лидер (лаймовая).
defineProps<{ k: string; win?: boolean }>()
</script>

<template>
  <span class="badge num" :class="{ win }">{{ k }}</span>
</template>

<style scoped>
.badge {
  display: inline-grid;
  place-items: center;
  flex: none;
  align-self: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--ink);
  color: var(--bg);
  font-size: 12px;
  font-weight: 600;
}

.badge.win {
  background: var(--lime);
  color: var(--on-tile);
}
</style>
