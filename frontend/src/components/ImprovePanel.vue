<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Download, ImagePlus, Loader2, RefreshCw, Replace, Sparkles } from 'lucide-vue-next'
import { addImproved, critiqueIssues, freeKeys, improvedFile, runImprove, state } from '../store'
import { IMPROVE_ETA_SEC } from '../lib/constants'
import type { Variant } from '../lib/types'

const props = defineProps<{ variant: Variant }>()
const v = computed(() => props.variant)

// выводы экспертов усиливают перерисовку — говорим об этом, чтобы было ясно, зачем их запрашивать
const withCritique = computed(() => critiqueIssues(v.value).length > 0)

// Секундомер ожидания: начало — в варианте, поэтому при переключении вариантов полоса не сбрасывается.
const elapsed = ref(0)
let timer = 0
watch(
  () => [v.value.improveStatus, v.value.improveStartedAt] as const,
  ([s, t]) => {
    clearInterval(timer)
    if (s !== 'loading' || !t) return
    const tick = () => (elapsed.value = Math.round((Date.now() - t) / 1000))
    tick()
    timer = window.setInterval(tick, 500)
  },
  { immediate: true },
)
onUnmounted(() => clearInterval(timer))

// полоса не доходит до конца, пока ответа нет: генерация иногда дольше обычного
const progress = computed(() => Math.min(95, (elapsed.value / IMPROVE_ETA_SEC) * 100))
const waitText = computed(() =>
  elapsed.value < IMPROVE_ETA_SEC ? `ещё около ${IMPROVE_ETA_SEC - elapsed.value} с` : 'почти готово…',
)

// нет свободного слота — предлагаем заменить один из вариантов
const replaceKeys = computed(() => (freeKeys.value.length ? [] : state.variants.map((x) => x.key)))

function download() {
  const file = improvedFile(v.value)
  if (!file || !v.value.improved) return
  const a = document.createElement('a')
  a.href = v.value.improved
  a.download = file.name
  a.click()
}
</script>

<template>
  <section class="improve">
    <div class="sec-head"><span class="label">Улучшенная обложка</span></div>

    <div v-if="v.improveStatus === 'loading'" class="wait" role="status">
      <span class="wait-title"><Loader2 :size="15" class="spin" /> Перерисовываем обложку…</span>
      <span class="prog"><i :style="{ width: `${progress}%` }" /></span>
      <span class="hint num">Обычно это занимает около {{ IMPROVE_ETA_SEC }} секунд · {{ waitText }}</span>
    </div>

    <div v-else-if="v.improveStatus === 'ready' && v.improved" class="result rise">
      <div class="pair">
        <figure>
          <img :src="v.url" alt="Исходная обложка" />
          <figcaption class="label">Было</figcaption>
        </figure>
        <figure>
          <img :src="v.improved" alt="Улучшенная обложка" />
          <figcaption class="label now">Стало</figcaption>
        </figure>
      </div>
      <p class="hint">Добавьте её как вариант — посчитаем заметность и сравним с исходной.</p>
      <div class="acts">
        <button v-if="!replaceKeys.length" class="btn primary" @click="addImproved(v)">
          <ImagePlus :size="15" /> Добавить как вариант
        </button>
        <div v-else class="replace" role="group" aria-label="Заменить вариант">
          <span class="hint"><Replace :size="13" /> Слоты заняты, заменить:</span>
          <button
            v-for="k in replaceKeys"
            :key="k"
            class="btn sm key num"
            :title="`Заменить вариант ${k}`"
            :aria-label="`Заменить вариант ${k}`"
            @click="addImproved(v, k)"
          >
            {{ k }}
          </button>
        </div>
        <button class="btn" @click="download"><Download :size="14" /> Скачать</button>
      </div>
      <button class="btn sm ghost again" @click="runImprove(v)"><RefreshCw :size="13" /> Нарисовать ещё раз</button>
    </div>

    <div v-else class="ask">
      <button class="btn primary big" @click="runImprove(v)"><Sparkles :size="16" /> Улучшить обложку</button>
      <span class="hint">
        Нейросеть перерисует обложку по выводам разбора — сохранит товар и бренд.
        <template v-if="withCritique">Учтём и замечания экспертов.</template>
      </span>
      <p v-if="v.improveStatus === 'error'" class="err" role="alert">{{ v.improveError }}</p>
    </div>
  </section>
</template>

<style scoped>
.improve {
  padding: 18px;
  margin: 0 -4px;
  border-radius: var(--radius);
  background: var(--lime-soft);
  border: 1px solid color-mix(in srgb, var(--lime) 60%, var(--line));
}

.sec-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.ask {
  display: grid;
  gap: 8px;
  justify-items: start;
}

.big {
  height: 40px;
  padding: 0 16px;
  font-size: 14px;
  white-space: normal;
  text-align: left;
}

.hint {
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

.err {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--bad);
}

.wait {
  display: grid;
  gap: 8px;
}

.wait-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.prog {
  display: block;
  height: 4px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--ink) 10%, transparent);
  overflow: hidden;
}

.prog i {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.5s linear;
}

.result {
  display: grid;
  gap: 12px;
}

.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

figure {
  margin: 0;
  display: grid;
  gap: 6px;
}

figure img {
  width: 100%;
  aspect-ratio: 3 / 4;
  /* обложки бывают разных пропорций — показываем целиком, без обрезки */
  object-fit: contain;
  border-radius: 8px;
  background: var(--sunken);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--ink) 10%, transparent);
}

.label.now {
  color: var(--ink);
}

.replace {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  flex-basis: 100%;
}

.replace .hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 2px;
}

.key {
  width: 30px;
  padding: 0;
  justify-content: center;
  font-weight: 600;
}

.acts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.again {
  justify-self: start;
  margin-left: -10px;
}
</style>
