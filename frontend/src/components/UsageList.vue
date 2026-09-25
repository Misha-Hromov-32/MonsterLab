<script setup lang="ts">
import { computed } from 'vue'
import { FEATURE_TITLES } from '../lib/constants'
import { availableFeatures } from '../store'
import type { FeatureLimits } from '../lib/types'

// Расход дневных лимитов по платным функциям: «2 из 3» и полоска.
const props = defineProps<{ usage: FeatureLimits; limits: FeatureLimits }>()

const rows = computed(() =>
  availableFeatures.value.map((f) => {
    const used = props.usage[f] ?? 0
    const limit = props.limits[f] ?? 0
    return { f, title: FEATURE_TITLES[f], used, limit, share: limit ? Math.min(1, used / limit) : 1 }
  }),
)
</script>

<template>
  <ul class="usage">
    <li v-for="r in rows" :key="r.f" :class="{ out: r.used >= r.limit }">
      <span class="t">{{ r.title }}</span>
      <span class="v num">{{ r.used }} из {{ r.limit }}</span>
      <span class="bar"><i :style="{ width: `${r.share * 100}%` }" /></span>
    </li>
  </ul>
</template>

<style scoped>
.usage {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

li {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px 12px;
  font-size: 13.5px;
}

.v {
  color: var(--ink-2);
}

.out .v {
  color: var(--bad);
}

.bar {
  grid-column: 1 / -1;
  height: 4px;
  border-radius: 2px;
  background: var(--panel-2);
  overflow: hidden;
}

.bar i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: var(--ink);
}

.out .bar i {
  background: var(--bad);
}
</style>
