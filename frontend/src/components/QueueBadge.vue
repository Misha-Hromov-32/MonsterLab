<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, Hourglass } from 'lucide-vue-next'
import { queue } from '../lib/queue'

// Плашка в углу: что из задач покупателя ждёт в очереди и что уже обрабатывается.
const jobs = computed(() => Object.values(queue.jobs))

const eta = (s: number) => (s < 60 ? `~${Math.max(1, s)} с` : `~${Math.round(s / 60)} мин`)
const line = (j: (typeof jobs.value)[number]) =>
  j.status === 'queued' ? `${j.position}-й в очереди · ${eta(j.eta_s)}` : `обрабатываем · ${eta(j.eta_s)}`
</script>

<template>
  <Transition name="q">
    <aside v-if="jobs.length" class="qbadge" role="status" aria-live="polite">
      <div v-for="j in jobs.slice(0, 3)" :key="j.id" class="row" :class="j.status">
        <Hourglass v-if="j.status === 'queued'" :size="14" aria-hidden="true" />
        <Loader2 v-else :size="14" class="spin" aria-hidden="true" />
        <span class="t">{{ j.title }}</span>
        <span class="s num">{{ line(j) }}</span>
      </div>
      <div v-if="jobs.length > 3" class="more">и ещё {{ jobs.length - 3 }}</div>
    </aside>
  </Transition>
</template>

<style scoped>
.qbadge {
  position: fixed;
  left: 16px;
  bottom: 16px;
  z-index: 40;
  display: grid;
  gap: 6px;
  min-width: 260px;
  max-width: calc(100vw - 32px);
  padding: 10px 14px;
  border-radius: 14px;
  background: var(--ink);
  color: var(--bg);
  box-shadow: var(--shadow);
  font-size: 12.5px;
}

.row {
  display: grid;
  grid-template-columns: 14px auto 1fr;
  align-items: center;
  gap: 8px;
}

.row.queued svg {
  color: var(--sun);
}

.row.running svg {
  color: var(--lime);
}

.t {
  font-weight: 600;
  white-space: nowrap;
}

.s {
  text-align: right;
  opacity: 0.75;
  white-space: nowrap;
}

.more {
  font-size: 11.5px;
  opacity: 0.6;
}

.q-enter-active,
.q-leave-active {
  transition:
    opacity 0.2s,
    transform 0.2s;
}

.q-enter-from,
.q-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
