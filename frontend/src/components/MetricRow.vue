<script setup lang="ts">
import { computed } from 'vue'
import { tone } from '../lib/format'
import { SCORE_GOOD, SCORE_WARN } from '../lib/constants'

const props = defineProps<{ title: string; value: number; detail: string; hint?: string }>()
const t = computed(() => tone(props.value))
// риски на шкале — те же пороги, что красят оценку
const marks = { '--warn-at': `${SCORE_WARN}%`, '--good-at': `${SCORE_GOOD}%` }
</script>

<template>
  <div class="metric" :title="hint">
    <div class="top">
      <span class="title">{{ title }}</span>
      <span class="val num" :class="t">{{ value }}</span>
    </div>
    <div class="track" :style="{ ...marks, '--value': `${Math.max(2, value)}%` }">
      <i class="fill" :class="t" />
      <i class="mark warn-at" />
      <i class="mark good-at" />
    </div>
    <span class="detail num">{{ detail }}</span>
  </div>
</template>

<style scoped>
.metric {
  display: grid;
  gap: 7px;
}

.top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.title {
  font-size: 13.5px;
  font-weight: 500;
}

.val {
  font-size: 22px;
  font-weight: 300;
  letter-spacing: -0.04em;
}

.val.good {
  color: var(--ink);
}
.val.warn {
  color: var(--warn);
}
.val.bad {
  color: var(--bad);
}

.track {
  position: relative;
  height: 4px;
  border-radius: 2px;
  background: var(--panel-2);
}

.fill {
  position: absolute;
  inset: 0 auto 0 0;
  width: var(--value);
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.2, 0.7, 0.2, 1);
}

.fill.good {
  background: var(--ink);
}
.fill.warn {
  background: var(--sun);
}
.fill.bad {
  background: var(--bad);
}

.mark {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 1px;
  background: var(--line-strong);
}

.mark.warn-at {
  left: var(--warn-at);
}

.mark.good-at {
  left: var(--good-at);
}

.detail {
  font-size: 11px;
  color: var(--ink-3);
}
</style>
