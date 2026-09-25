<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ImagePlus, Loader2, Play, X } from 'lucide-vue-next'
import HeatImage from './HeatImage.vue'
import KeyBadge from './KeyBadge.vue'
import Segmented from './Segmented.vue'
import CompetitorSearch from './CompetitorSearch.vue'
import { addCompetitors, features, ready, removeCompetitor, runShelf, state } from '../store'
import { MAX_COMPETITORS } from '../lib/constants'
import { pct, tone } from '../lib/format'
import { SHELF_OVERLAY_MODES } from '../lib/overlay'
import { useFilePicker } from '../lib/useFilePicker'
import type { Key, OverlayMode } from '../lib/types'

const over = ref(false)
const shown = ref<string>('')
const pick = useFilePicker(addCompetitors)

const layouts = [
  { id: 'mobile' as const, title: 'Телефон · 2 колонки' },
  { id: 'desktop' as const, title: 'Компьютер · 5 колонок' },
]
const shelfMode = computed({
  get: () => (state.mode === 'gaze' ? 'heat' : state.mode),
  set: (m: OverlayMode) => (state.mode = m),
})

// Оценка времени повторяет раскладку сервера (backend/app/core/shelf.py: LAYOUTS, MAX_POSITIONS) —
// меняются там, поправьте и здесь.
const SLOTS_MOBILE = 6 // карточек на полке телефона
const SLOTS_DESKTOP = 10 // карточек на полке компьютера
const MAX_POSITIONS = 4 // на скольких позициях проверяется каждый вариант
// ≈ время одного прогона нейросети на сервере с 2 vCPU
const SEC_PER_RUN = 2
const MIN_ETA_SEC = 6

const runs = computed(() => {
  const n = ready.value.length
  if (!state.competitors.length) return n
  const slots = Math.min(state.layout === 'mobile' ? SLOTS_MOBILE : SLOTS_DESKTOP, state.competitors.length + 1)
  return n * Math.min(MAX_POSITIONS, slots)
})
const eta = computed(() => Math.max(MIN_ETA_SEC, runs.value * SEC_PER_RUN))
const canRun = computed(() => ready.value.length >= 2 || (ready.value.length >= 1 && state.competitors.length >= 1))

function onDrop(e: DragEvent) {
  over.value = false
  if (e.dataTransfer?.files.length) addCompetitors(e.dataTransfer.files)
}

// секундомер, пока сервер считает полки; начало берём из стора — при возврате на вкладку
// индикатор продолжает с того же места, а не начинается заново
const elapsed = ref(0)
let timer = 0
watch(
  () => state.shelfStatus,
  (s) => {
    clearInterval(timer)
    if (s === 'loading') {
      const tick = () => (elapsed.value = Math.round((Date.now() - state.shelfStartedAt) / 1000))
      tick()
      timer = window.setInterval(tick, 500)
    }
  },
  { immediate: true },
)

// число может не прийти (например, пустая картинка) — показываем прочерк, а не падаем
const times = (n: number | null | undefined) => (typeof n === 'number' && Number.isFinite(n) ? n.toFixed(2) : '—')
onUnmounted(() => clearInterval(timer))

// Выделяющимся считаем вариант, забирающий хотя бы на 15% больше «положенного» по месту:
// меньший перевес укладывается в разброс между прогонами.
const STANDOUT = 1.15

const res = computed(() => state.shelf)
const keys = computed(() => (res.value ? (Object.keys(res.value.results) as Key[]) : []))
const sorted = computed(() => {
  const r = res.value
  return r ? [...keys.value].sort((a, b) => r.results[b].stop_power - r.results[a].stop_power) : []
})
const top = computed(() => {
  const r = res.value
  const k = sorted.value[0]
  return r && k ? { key: k, stop: r.results[k].stop_power } : null
})
// immediate — при возврате на вкладку результат уже есть, и сразу нужна выбранная полка
watch(
  res,
  (r) => {
    if (r) shown.value = r.mode === 'variants' ? '_all' : (sorted.value[0] ?? '')
  },
  { immediate: true },
)
const mosaic = computed(() =>
  res.value ? (res.value.mosaics[shown.value] ?? Object.values(res.value.mosaics)[0]) : null,
)
const maxStop = computed(() => {
  const r = res.value
  return Math.max(2, ...(r ? sorted.value.map((k) => r.results[k].stop_power) : []))
})
</script>

<template>
  <div class="shelf scroll-y">
    <header class="head">
      <span class="label">Тест полки</span>
      <h2>Заметят ли карточку среди соседей?</h2>
      <p>
        Вариант ставится в сетку выдачи на разные позиции, а конкуренты перемешиваются. Мы считаем, какую долю внимания
        всей полки забирает ваша карточка. ×1.0 — карточку замечают «как все», больше — она выделяется.
      </p>
    </header>

    <section class="setup">
      <div class="block">
        <span class="label">Раскладка</span>
        <Segmented v-model="state.layout" :options="layouts" label="Раскладка" />
      </div>

      <div class="block grow">
        <span class="label">Конкуренты в выдаче · {{ state.competitors.length }}/{{ MAX_COMPETITORS }}</span>
        <div
          class="comp"
          :class="{ over }"
          data-own-drop
          @dragover.prevent="over = true"
          @dragleave="over = false"
          @drop.prevent="onDrop"
        >
          <div v-for="(c, i) in state.competitors" :key="c.url" class="cthumb">
            <img :src="c.url" alt="" />
            <button class="rm" title="Убрать" :aria-label="`Убрать конкурента ${i + 1}`" @click="removeCompetitor(i)">
              <X :size="12" />
            </button>
          </div>
          <button class="add" @click="pick()">
            <ImagePlus :size="18" />
            <span>{{ state.competitors.length ? 'Ещё' : 'Добавьте обложки конкурентов' }}</span>
          </button>
        </div>
        <CompetitorSearch v-if="features.competitors" />
        <p v-if="!state.competitors.length" class="hint">
          Без конкурентов ваши варианты соревнуются друг с другом. Обложки конкурентов можно сохранить из выдачи по
          вашему запросу.
        </p>
        <p v-else class="hint">Каждый вариант встанет в выдачу рядом с этими обложками на разные позиции.</p>
      </div>

      <div class="block run">
        <button class="btn primary" :disabled="!canRun || state.shelfStatus === 'loading'" @click="runShelf">
          <Loader2 v-if="state.shelfStatus === 'loading'" :size="15" class="spin" />
          <Play v-else :size="15" />
          {{ state.shelfStatus === 'loading' ? 'Считаем…' : 'Запустить тест' }}
        </button>
        <span v-if="state.shelfStatus === 'loading'" class="est">
          Расставляем карточки по полке…
          <span class="prog"><i :style="{ width: `${Math.min(96, (elapsed / eta) * 100)}%` }" /></span>
        </span>
        <span v-else-if="canRun" class="est">займёт {{ eta <= 20 ? 'несколько секунд' : 'меньше минуты' }}</span>
        <span v-else class="est">нужно два варианта или хотя бы один конкурент</span>
      </div>
    </section>

    <p v-if="state.shelfStatus === 'error'" class="err">{{ state.shelfError }}</p>

    <section v-if="res && mosaic" class="result rise">
      <div class="view">
        <div class="view-bar">
          <Segmented v-model="shelfMode" :options="SHELF_OVERLAY_MODES" size="sm" label="Режим наложения" />
          <div v-if="res.mode === 'competitors' && keys.length > 1" class="pick">
            <span class="label">Показать</span>
            <button
              v-for="k in keys"
              :key="k"
              class="kbtn num"
              :class="{ on: shown === k }"
              :aria-pressed="shown === k"
              @click="shown = k"
            >
              {{ k }}
            </button>
          </div>
        </div>
        <div class="mosaic" :class="res.layout">
          <HeatImage
            :src="mosaic.image"
            :width="mosaic.width"
            :height="mosaic.height"
            :grid="mosaic.grid"
            :mode="shelfMode"
            :opacity="state.opacity"
            :highlight="mosaic.target !== null ? mosaic.rects[mosaic.target] : null"
            compact
          />
          <template v-if="mosaic.order">
            <span
              v-for="(k, i) in mosaic.order"
              :key="k"
              class="tag num"
              :style="{ left: `${mosaic.rects[i].x * 100}%`, top: `${mosaic.rects[i].y * 100}%` }"
              >{{ k }}</span
            >
          </template>
        </div>
      </div>

      <div class="scores">
        <span class="label">Заметность на полке</span>
        <div v-for="(k, i) in sorted" :key="k" class="srow">
          <div class="stop-head">
            <KeyBadge :k="k" :win="i === 0" />
            <span class="stop num" :class="res.results[k].stop_power >= 1 ? 'up' : 'down'"
              >×{{ times(res.results[k].stop_power) }}</span
            >
            <span class="num sub"
              >{{ pct(res.results[k].share, 1) }} внимания полки при средних {{ pct(res.results[k].fair, 1) }}</span
            >
          </div>
          <div class="sbar">
            <i :style="{ width: `${(res.results[k].stop_power / maxStop) * 100}%` }" :class="{ win: i === 0 }" />
            <i class="fair" :style="{ left: `${(1 / maxStop) * 100}%` }" />
          </div>
          <div class="dist num">
            <span>непохожесть на {{ res.mode === 'competitors' ? 'конкурентов' : 'соседей' }}</span>
            <b :class="tone(res.results[k].distinct)">{{ res.results[k].distinct }}</b>
          </div>
        </div>
        <p class="concl">
          <template v-if="top && top.stop >= STANDOUT">
            <b>{{ top.key }}</b> забирает на {{ Math.round((top.stop - 1) * 100) }}% больше внимания, чем положено по
            месту на полке.
          </template>
          <template v-else>
            Ни один вариант заметно не выделяется: карточки сливаются с
            {{ res.mode === 'competitors' ? 'конкурентами' : 'друг другом' }}. Нужен контрастный цвет фона или крупный
            акцент.
          </template>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.shelf {
  flex: 1;
  padding: 26px clamp(20px, 3vw, 40px) 48px;
  display: grid;
  align-content: start;
  gap: 26px;
  min-height: 0;
}

.head h2 {
  margin: 8px 0 8px;
  font-size: 30px;
  font-weight: 300;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.head p {
  margin: 0;
  max-width: 720px;
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.55;
}

.setup {
  display: flex;
  gap: 28px;
  align-items: flex-start;
  flex-wrap: wrap;
  padding: 20px 22px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
}

.block {
  display: grid;
  gap: 10px;
}

.grow {
  flex: 1;
  min-width: 280px;
}

.comp {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px;
  border: 1.5px dashed var(--line-strong);
  border-radius: 10px;
  transition:
    border-color 0.15s,
    background 0.15s;
}

.comp.over {
  border-color: var(--ink);
  background: var(--panel-2);
}

.cthumb {
  position: relative;
  width: 48px;
  height: 64px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--sunken);
}

.cthumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.rm {
  position: absolute;
  right: 2px;
  top: 2px;
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  opacity: 0;
  transition: opacity 0.12s;
}

.cthumb:hover .rm,
.rm:focus-visible {
  opacity: 1;
}

/* на тачскринах наведения нет — крестик виден всегда */
@media (hover: none) {
  .rm {
    opacity: 1;
  }
}

.add {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 64px;
  padding: 0 14px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13px;
}

.add:hover {
  background: var(--panel-2);
  color: var(--ink);
}

.hint {
  margin: 0;
  font-size: 10.5px;
  color: var(--ink-3);
  line-height: 1.5;
}

.run {
  justify-items: start;
  align-self: center;
}

.est {
  display: grid;
  gap: 6px;
  font-size: 11px;
  color: var(--ink-3);
}

.prog {
  display: block;
  width: 150px;
  height: 3px;
  border-radius: 2px;
  background: var(--panel-2);
  overflow: hidden;
}

.prog i {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.5s linear;
}

.err {
  margin: 0;
  color: var(--bad);
}

.result {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(300px, 1fr);
  gap: 32px;
  align-items: start;
}

.view {
  display: grid;
  gap: 12px;
}

.view-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.pick {
  display: flex;
  align-items: center;
  gap: 6px;
}

.kbtn {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--panel);
  font-size: 12px;
  font-weight: 600;
}

.kbtn.on {
  background: var(--ink);
  color: var(--bg);
  border-color: var(--ink);
}

.mosaic {
  position: relative;
  box-shadow: var(--shadow);
  border-radius: 6px;
}

.mosaic.mobile {
  max-width: 460px;
}

.tag {
  position: absolute;
  margin: 8px;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 5px;
  background: var(--ink);
  color: var(--bg);
  font-size: 11px;
  font-weight: 600;
  pointer-events: none;
}

.scores {
  display: grid;
  gap: 20px;
}

.srow {
  display: grid;
  gap: 8px;
}

.stop-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.stop {
  font-size: 30px;
  font-weight: 300;
  letter-spacing: -0.03em;
}

.stop.down {
  color: var(--ink-3);
}

.sub {
  font-size: 11px;
  color: var(--ink-3);
}

.sbar {
  position: relative;
  height: 8px;
  border-radius: 4px;
  background: var(--panel-2);
}

.sbar i {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 4px;
  background: var(--ink-3);
  transition: width 0.6s cubic-bezier(0.2, 0.7, 0.2, 1);
}

.sbar i.win {
  background: var(--ink);
}

.sbar i.fair {
  inset: -4px auto -4px auto;
  width: 2px;
  background: var(--ink);
  border-radius: 1px;
}

.dist {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--ink-3);
}

.dist b.good {
  color: var(--good);
}
.dist b.warn {
  color: var(--warn);
}
.dist b.bad {
  color: var(--bad);
}

.concl {
  margin: 4px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 14px;
  line-height: 1.5;
}

@media (max-width: 1100px) {
  .result {
    grid-template-columns: 1fr;
  }
}
</style>
