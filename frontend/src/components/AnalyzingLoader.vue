<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Check } from 'lucide-vue-next'
import MonsterMark from './MonsterMark.vue'

defineProps<{ src: string }>()

// Анализ идёт одним запросом, поэтому этапы показываем по таймеру — так видно, что работа идёт.
// Темп подобран на глаз под обычное время ответа: этапы не должны заметно обгонять результат.
const STAGES = [
  'Загружаем обложку',
  'Ищем, куда посмотрит покупатель',
  'Считаем фокус и читаемость',
  'Готовим рекомендации',
]
/** Смена этапа; последний этап держится, пока не придёт ответ. */
const STAGE_MS = 1500
/** Постоянная времени прогресса: за столько миллисекунд полоса проходит ~63% пути. */
const PROGRESS_TAU_MS = 2600
const PROGRESS_MAX = 94
const stage = ref(0)
const progress = ref(4)
let timer = 0
let raf = 0

onMounted(() => {
  const t0 = performance.now()
  timer = window.setInterval(() => (stage.value = Math.min(STAGES.length - 1, stage.value + 1)), STAGE_MS)
  // прогресс асимптотически подбирается к PROGRESS_MAX, пока сервер не ответит
  const tick = (t: number) => {
    progress.value = PROGRESS_MAX * (1 - Math.exp(-(t - t0) / PROGRESS_TAU_MS))
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
})
onUnmounted(() => {
  clearInterval(timer)
  cancelAnimationFrame(raf)
})
</script>

<template>
  <div class="loader" role="status" aria-live="polite">
    <div class="pic">
      <img :src="src" alt="" />
      <div class="grid" />
      <div class="scan" />
      <span class="corner tl" /><span class="corner tr" /><span class="corner bl" /><span class="corner br" />
    </div>

    <div class="card">
      <!-- глаз из логотипа: рассматривает обложку и моргает -->
      <MonsterMark :size="56" animated />

      <ol class="steps">
        <li v-for="(s, i) in STAGES" :key="s" :class="{ done: i < stage, now: i === stage }">
          <span class="mark"><Check v-if="i < stage" :size="12" :stroke-width="3" /></span>
          {{ s }}<template v-if="i === stage">…</template>
        </li>
      </ol>

      <div class="bar"><i :style="{ width: `${progress}%` }" /></div>
    </div>
  </div>
</template>

<style scoped>
.loader {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
}

/* обложка со сканером */
.pic {
  position: relative;
  max-width: 100%;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 30px 60px -30px rgba(0, 0, 0, 0.4);
}

.pic img {
  display: block;
  max-width: 100%;
  max-height: calc(100vh - 250px);
  filter: saturate(0.6) brightness(0.92);
}

/* сетка точек: вспыхивает там, где прошёл сканер */
.grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(255, 255, 255, 0.85) 1.2px, transparent 1.4px);
  background-size: 18px 18px;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 var(--scan), transparent calc(var(--scan) + 1%));
  mask-image: linear-gradient(to bottom, transparent 0, #000 var(--scan), transparent calc(var(--scan) + 1%));
  animation: scanvar 2.4s cubic-bezier(0.45, 0, 0.55, 1) infinite;
  opacity: 0.55;
}

.scan {
  position: absolute;
  left: 0;
  right: 0;
  height: 22%;
  top: -22%;
  background: linear-gradient(
    to bottom,
    transparent,
    color-mix(in srgb, var(--lime) 28%, transparent) 70%,
    color-mix(in srgb, var(--lime) 90%, transparent) 98%,
    transparent
  );
  border-bottom: 2px solid var(--lime);
  box-shadow: 0 8px 24px color-mix(in srgb, var(--lime) 55%, transparent);
  animation: scan 2.4s cubic-bezier(0.45, 0, 0.55, 1) infinite;
}

@property --scan {
  syntax: '<percentage>';
  inherits: false;
  initial-value: 0%;
}

@keyframes scanvar {
  from {
    --scan: 0%;
  }
  to {
    --scan: 100%;
  }
}

@keyframes scan {
  from {
    top: -22%;
  }
  to {
    top: 100%;
  }
}

.corner {
  position: absolute;
  width: 18px;
  height: 18px;
  border: 0 solid var(--lime);
}
.tl {
  left: 10px;
  top: 10px;
  border-width: 2px 0 0 2px;
}
.tr {
  right: 10px;
  top: 10px;
  border-width: 2px 2px 0 0;
}
.bl {
  left: 10px;
  bottom: 10px;
  border-width: 0 0 2px 2px;
}
.br {
  right: 10px;
  bottom: 10px;
  border-width: 0 2px 2px 0;
}

/* карточка с этапами */
.card {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  display: grid;
  justify-items: center;
  gap: 16px;
  width: min(92%, 320px);
  padding: 22px 22px 20px;
  border-radius: 14px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  width: 100%;
}

.steps li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  letter-spacing: -0.02em;
  color: var(--ink-3);
  transition: color 0.3s;
}

.steps li.now {
  color: var(--ink);
}

.steps li.done {
  color: var(--ink-2);
}

.mark {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex: none;
  border-radius: 50%;
  border: 1.5px solid var(--line-strong);
  transition:
    background 0.3s,
    border-color 0.3s;
}

.now .mark {
  border-color: var(--ink);
  border-top-color: transparent;
  animation: spin 0.8s linear infinite;
}

.done .mark {
  border-color: var(--lime);
  background: var(--lime);
  color: var(--on-tile);
}

.bar {
  width: 100%;
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
</style>
