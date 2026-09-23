<script setup lang="ts">
import MonsterMark from './MonsterMark.vue'

withDefaults(defineProps<{ size?: number; wordmark?: boolean; sub?: string }>(), { size: 32, wordmark: true })
</script>

<template>
  <span class="logo">
    <MonsterMark :size="size" />
    <span v-if="wordmark" class="words">
      <span class="wm">Monster <span class="lab">Lab</span></span>
      <span v-if="sub" class="sub">{{ sub }}</span>
    </span>
  </span>
</template>

<style scoped>
.logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ink);
}

.words {
  display: grid;
  line-height: 1.05;
}

.wm {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.045em;
  white-space: nowrap;
}

.lab {
  font-weight: 300;
}

.sub {
  font-size: 11px;
  color: var(--ink-3);
  letter-spacing: -0.01em;
}
</style>
