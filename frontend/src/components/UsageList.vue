<script setup lang="ts">
import { computed } from 'vue'
import { FEATURE_TITLES } from '../lib/constants'
import { availableFeatures } from '../store'
import type { FeatureLimits } from '../lib/types'

// Расход квот по функциям: «2 из 3» и полоска. У демо — на всё время, у тарифа — на период оплаты.
const props = defineProps<{ usage: FeatureLimits; limits: FeatureLimits; bonus?: FeatureLimits }>()

const rows = computed(() =>
  availableFeatures.value.map((f) => {
    const used = props.usage[f] ?? 0
    const limit = props.limits[f] ?? 0
    const bonus = props.bonus?.[f] ?? 0
    return { f, title: FEATURE_TITLES[f], used, limit, bonus, share: limit ? Math.min(1, used / limit) : 1 }
  }),
)
</script>

<template>
  <ul class="usage">
    <li v-for="r in rows" :key="r.f" :class="{ out: r.used >= r.limit && !r.bonus }">
      <span class="t">{{ r.title }}</span>
      <span class="v num"
        >{{ r.used }} из {{ r.limit
        }}<b v-if="r.bonus" class="bonus" title="Бонусные запуски по промокоду">+{{ r.bonus }}</b></span
      >
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

.bonus {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--brand) 12%, transparent);
  color: var(--brand);
  font-size: 11.5px;
  font-weight: 600;
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
