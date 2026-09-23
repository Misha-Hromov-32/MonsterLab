<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Crop, Download, Smartphone, RefreshCw } from 'lucide-vue-next'
import HeatImage from './HeatImage.vue'
import Segmented from './Segmented.vue'
import Inspector from './Inspector.vue'
import AnalyzingLoader from './AnalyzingLoader.vue'
import { analyze, current, state } from '../store'
import { AOI_LABELS } from '../lib/constants'
import { exportPng, GRADIENT_CSS } from '../lib/heat'
import { hasOpacity, OVERLAY_MODES } from '../lib/overlay'

const drawing = ref(false)
const preview = ref(false)
const area = ref<HTMLDivElement>()
const box = ref({ w: 0, h: 0 })
let ro: ResizeObserver | undefined

onMounted(() => {
  ro = new ResizeObserver(([e]) => (box.value = { w: e.contentRect.width, h: e.contentRect.height }))
  if (area.value) ro.observe(area.value)
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  ro?.disconnect()
  window.removeEventListener('keydown', onKey)
})

// Горячие клавиши работают только «голыми»: Ctrl+1 / Ctrl+Z принадлежат браузеру, а в полях ввода — тексту.
function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey) return
  if (e.target instanceof Element && e.target.closest('input, textarea, select, [contenteditable]')) return
  const n = Number(e.key)
  const key = e.key.toLowerCase()
  if (n >= 1 && n <= OVERLAY_MODES.length) state.mode = OVERLAY_MODES[n - 1].id
  // «я» — та же клавиша в русской раскладке
  else if (key === 'z' || key === 'я') drawing.value = !drawing.value
  else if (e.key === 'Escape') drawing.value = false
}

const a = computed(() => current.value?.analysis)

// вписываем картинку в доступную область по ширине и высоте
const fit = computed(() => {
  if (!a.value || !box.value.w) return { width: '100%' }
  const ratio = a.value.width / a.value.height
  const w = Math.min(box.value.w, box.value.h * ratio)
  return { width: `${Math.floor(w)}px` }
})

async function download() {
  const x = current.value
  const an = a.value
  if (!x || !an) return
  const base = x.name.replace(/\.[^.]+$/, '')
  await exportPng({
    src: x.url,
    grid: an.grid,
    mode: state.mode === 'fog' ? 'fog' : 'heat',
    opacity: state.opacity,
    title: `Вариант ${x.key} · индекс заметности ${an.index}/100`,
    lines: [
      `фокус ${an.scores.focus} · лёгкость восприятия ${an.scores.ease} · превью ${an.scores.thumb} · контраст ${an.scores.contrast}`,
      `половина внимания — на ${Math.round(an.raw.area50 * 100)}% площади · Monster Lab`,
    ],
    filename: `${base}__внимание.png`,
  })
}

function createAoi(rect: { x: number; y: number; w: number; h: number }) {
  const v = current.value
  if (!v) return
  const used = new Set(v.aois.map((x) => x.label))
  const label = AOI_LABELS.find((l) => !used.has(l)) ?? `Зона ${v.aois.length + 1}`
  v.aois.push({ id: Math.random().toString(36).slice(2, 9), label, ...rect })
}
</script>

<template>
  <div v-if="current" class="analyze">
    <section class="stage">
      <div class="toolbar">
        <div class="caption num">
          <span class="fig">Вариант {{ current.key }}</span>
          <span class="fname" :title="current.name">{{ current.name }}</span>
        </div>
        <div class="controls">
          <Segmented v-model="state.mode" :options="OVERLAY_MODES" label="Режим наложения" />
          <label class="opacity" :class="{ hidden: !hasOpacity(state.mode) }" title="Плотность наложения">
            <input
              v-model.number="state.opacity"
              type="range"
              min="0.2"
              max="1"
              step="0.05"
              aria-label="Плотность наложения"
              :disabled="!hasOpacity(state.mode)"
            />
          </label>
          <button
            class="btn sm"
            :class="{ primary: drawing }"
            :aria-pressed="drawing"
            :disabled="!a"
            title="Нарисуйте рамку вокруг товара или оффера (Z)"
            @click="drawing = !drawing"
          >
            <Crop :size="14" /> Зона
          </button>
          <button
            class="btn sm"
            :class="{ primary: preview }"
            :aria-pressed="preview"
            :disabled="!a"
            title="Как карточка выглядит в мобильной выдаче"
            @click="preview = !preview"
          >
            <Smartphone :size="14" /> Превью
          </button>
          <button
            class="btn sm icon"
            :disabled="!a"
            title="Скачать PNG с картой внимания"
            aria-label="Скачать PNG"
            @click="download"
          >
            <Download :size="14" />
          </button>
        </div>
      </div>

      <div ref="area" class="area">
        <AnalyzingLoader v-if="current.status === 'loading'" :key="current.url" :src="current.url" />
        <div v-else-if="current.status === 'error'" class="wait">
          <div class="wait-msg err">
            <strong>Не получилось проанализировать</strong>
            <span>{{ current.error }}</span>
            <button class="btn sm" @click="analyze(current)"><RefreshCw :size="14" /> Повторить</button>
          </div>
        </div>
        <div v-else-if="a" class="frame" :style="fit">
          <HeatImage
            :src="current.url"
            :width="a.width"
            :height="a.height"
            :grid="a.grid"
            :fixations="a.fixations"
            :mode="state.mode"
            :opacity="state.opacity"
            :aois="current.aois"
            :editable="drawing"
            @create="createAoi"
          />
          <span class="tick tl" /><span class="tick tr" /><span class="tick bl" /><span class="tick br" />
        </div>

        <div v-if="preview && a" class="phone rise">
          <span class="label">Так карточка выглядит в ленте телефона</span>
          <div class="feed">
            <div class="card-mini">
              <img :src="current.url" alt="" />
              <i class="bar w80" /><i class="bar w50" />
            </div>
            <div class="card-mini ph">
              <div class="ph-img" />
              <i class="bar w70" /><i class="bar w40" />
            </div>
          </div>
        </div>
      </div>

      <div class="legend">
        <template v-if="state.mode === 'heat'">
          <span class="num">мало</span>
          <span class="scale" :style="{ background: GRADIENT_CSS }" />
          <span class="num">много внимания</span>
        </template>
        <span v-else-if="state.mode === 'contours'" class="iso-legend num">
          <span><i class="sw acc" /> 25% внимания</span>
          <span><i class="sw" /> 50%</span>
          <span><i class="sw dash" /> 75%</span>
        </span>
        <span v-else-if="state.mode === 'gaze'" class="num">Порядок просмотра · 1 — куда взгляд упадёт первым</span>
        <span v-else-if="state.mode === 'fog'" class="num"
          >Проявлено то, что покупатель успеет заметить за 2–3 секунды</span
        >
        <span v-else class="num">Клавиши 1–5 переключают режимы, Z — нарисовать зону</span>
      </div>
    </section>

    <!-- key: у каждого варианта своё состояние панели (например, выбранный эксперт) -->
    <Inspector v-if="a" :key="current.key" :variant="current" :analysis="a" />
    <aside v-else class="inspector-skeleton" />
  </div>
</template>

<style scoped>
.analyze {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 384px;
  min-height: 0;
}

.stage {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto 1fr auto;
  min-width: 0;
  min-height: 0;
  background: var(--stage);
  background-image: radial-gradient(color-mix(in srgb, var(--ink) 9%, transparent) 1px, transparent 1px);
  background-size: 18px 18px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 20px;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}

.caption {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
  font-size: 11.5px;
  color: var(--ink-3);
}

.fig {
  color: var(--ink);
  font-weight: 600;
}

.fname {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
  color: var(--ink-2);
}

.controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
  max-width: 100%;
}

/* на узком экране пять режимов не помещаются — листаются внутри переключателя, страница не уезжает вбок */
.controls :deep(.seg) {
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}

.opacity input {
  width: 84px;
  accent-color: var(--ink);
}

.opacity.hidden {
  visibility: hidden;
}

.area {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 0;
  margin: 28px 32px;
}

.frame {
  position: relative;
  box-shadow:
    0 30px 60px -30px rgba(0, 0, 0, 0.45),
    0 0 0 1px color-mix(in srgb, var(--ink) 12%, transparent);
}

.tick {
  position: absolute;
  width: 12px;
  height: 12px;
  border-color: var(--ink-3);
  border-style: solid;
  pointer-events: none;
}
.tl {
  left: -9px;
  top: -9px;
  border-width: 1px 0 0 1px;
}
.tr {
  right: -9px;
  top: -9px;
  border-width: 1px 1px 0 0;
}
.bl {
  left: -9px;
  bottom: -9px;
  border-width: 0 0 1px 1px;
}
.br {
  right: -9px;
  bottom: -9px;
  border-width: 0 1px 1px 0;
}

.wait {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
}

.wait-msg {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 20px 28px;
  border-radius: 12px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  text-align: center;
  max-width: 360px;
}

.wait-msg.err strong {
  color: var(--bad);
}

.phone {
  position: absolute;
  right: 0;
  bottom: 0;
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 14px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.feed {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 170px));
  gap: 8px;
}

.card-mini {
  display: grid;
  gap: 5px;
}

.card-mini img,
.ph-img {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: 8px;
  background: var(--panel-2);
}

.bar {
  display: block;
  height: 7px;
  border-radius: 3px;
  background: var(--panel-2);
}
.card-mini:not(.ph) .bar {
  background: var(--line-strong);
}
.w80 {
  width: 80%;
}
.w70 {
  width: 70%;
}
.w50 {
  width: 50%;
}
.w40 {
  width: 40%;
}

.legend {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-top: 1px solid var(--line);
  background: var(--bg);
  font-size: 11px;
  color: var(--ink-3);
  min-height: 40px;
}

.scale {
  width: 140px;
  height: 6px;
  border-radius: 3px;
}

.iso-legend {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}

.sw {
  display: inline-block;
  width: 14px;
  height: 0;
  border-top: 2px solid var(--ink-2);
  vertical-align: middle;
}
.sw.acc {
  border-color: var(--accent);
}
.sw.dash {
  border-top-style: dashed;
}

.inspector-skeleton {
  border-left: 1px solid var(--line);
  background: var(--bg);
}

@media (max-width: 1180px) {
  .analyze {
    grid-template-columns: minmax(0, 1fr) 330px;
  }
}

@media (max-width: 900px) {
  .analyze {
    grid-template-columns: minmax(0, 1fr);
  }
  .area {
    min-width: 0;
    margin: 16px;
    min-height: 60vh;
  }
  .phone {
    position: static;
    margin-top: 12px;
  }
}
</style>
