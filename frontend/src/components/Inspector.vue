<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import MetricRow from './MetricRow.vue'
import CritiquePanel from './CritiquePanel.vue'
import ImprovePanel from './ImprovePanel.vue'
import { features } from '../store'
import { aoiStat } from '../lib/heat'
import { pct, tone } from '../lib/format'
import { AOI_LABELS, AOI_LIFT_OK, AOI_LIFT_STRONG, SCORE_GOOD } from '../lib/constants'
import type { Analysis, Note, Variant } from '../lib/types'

// Инспектор показывается только для проанализированного варианта — анализ передаётся отдельно, уже без undefined.
const props = defineProps<{ variant: Variant; analysis: Analysis }>()
const a = computed(() => props.analysis)

// Вердикт по индексу строже общих порогов: «сильная» — только заметно выше «хорошо».
const VERDICTS: [number, string][] = [
  [70, 'Сильная обложка'],
  [50, 'Рабочая, есть что усилить'],
  [35, 'Слабая'],
]
const verdict = computed(() => VERDICTS.find(([min]) => a.value.index >= min)?.[1] ?? 'Требует переделки')

// Пороги подсказок — как в backend/app/core/metrics.py: notes(), чтобы строка не спорила с выводами.
const THUMB_GOOD = 75
const THUMB_BAD = 45
const CONTRAST_BAD = 35

const thumbText = computed(() => {
  const t = a.value.scores.thumb
  if (t >= THUMB_GOOD) return 'в ленте телефона всё читается'
  if (t >= THUMB_BAD) return 'часть мелких деталей в ленте потеряется'
  return 'мелкий текст в ленте не прочитать'
})
const contrastText = computed(() => {
  const c = a.value.scores.contrast
  if (c >= SCORE_GOOD) return 'товар хорошо отделён от фона'
  if (c >= CONTRAST_BAD) return 'контраст средний'
  return 'картинка «плоская», товар сливается с фоном'
})

// Хвалим зону в заметках, только если перевес внимания очевиден — выше порога «сильной» зоны в списке.
const AOI_LIFT_PRAISE = 2.2

const aois = computed(() => props.variant.aois.map((x) => ({ x, s: aoiStat(a.value.grid, x) })))

const liftTone = (lift: number) => (lift >= AOI_LIFT_STRONG ? 'good' : lift < AOI_LIFT_OK ? 'bad' : '')

const aoiNotes = computed(() => {
  const out: Note[] = []
  for (const { x, s } of aois.value) {
    const share = Math.round(s.share * 100)
    if (s.lift < AOI_LIFT_OK)
      out.push({
        level: 'bad',
        title: `«${x.label}» теряется`,
        text: `Зона занимает ${pct(s.area)} кадра, а получает лишь ${share}% внимания — меньше, чем положено по площади. Сделайте её контрастнее или крупнее.`,
      })
    else if (s.lift >= AOI_LIFT_PRAISE)
      out.push({
        level: 'good',
        title: `«${x.label}» притягивает взгляд`,
        text: `${share}% внимания при ${pct(s.area)} площади — в ${s.lift.toFixed(1)} раза больше, чем «положено».`,
      })
  }
  return out
})

const notes = computed(() => [...aoiNotes.value, ...a.value.notes])

function remove(id: string) {
  const i = props.variant.aois.findIndex((x) => x.id === id)
  if (i >= 0) props.variant.aois.splice(i, 1)
}
</script>

<template>
  <aside class="inspector scroll-y">
    <section class="hero">
      <span class="label">Индекс заметности</span>
      <div class="big">
        <span class="n num" :class="tone(a.index)">{{ a.index }}</span>
        <span class="of num">/100</span>
      </div>
      <p class="verdict">{{ verdict }}</p>
      <p class="lead">Насколько быстро покупатель считает обложку и поймёт, куда смотреть.</p>
    </section>

    <section>
      <div class="sec-head"><span class="label">Метрики</span></div>
      <div class="metrics">
        <MetricRow
          title="Фокус внимания"
          :value="a.scores.focus"
          :detail="`половина взгляда — на ${pct(a.raw.area50)} площади · центров внимания: ${a.raw.hotspots}`"
          hint="Насколько компактно собрано внимание. Меньше площадь — сильнее фокус."
        />
        <MetricRow
          title="Лёгкость восприятия"
          :value="a.scores.ease"
          :detail="`элементов на обложке: ${a.raw.elements} · заметных цветов: ${a.raw.colors}`"
          hint="Чем меньше плашек, надписей и цветов, тем быстрее обложка считывается."
        />
        <MetricRow
          title="Читаемость на превью"
          :value="a.scores.thumb"
          :detail="thumbText"
          hint="Останутся ли надписи и детали различимы в маленькой карточке в ленте телефона."
        />
        <MetricRow
          title="Контраст"
          :value="a.scores.contrast"
          :detail="contrastText"
          hint="Насколько товар и надписи отделены от фона."
        />
      </div>
    </section>

    <section>
      <div class="sec-head">
        <span class="label">Зоны интереса</span>
        <span v-if="aois.length" class="label num">внимание</span>
      </div>
      <p v-if="!aois.length" class="empty-hint">
        Нажмите <b>Зона</b> над картинкой и обведите товар, оффер или цену — покажем, какую долю внимания они получают.
      </p>
      <ul v-else class="aois">
        <li v-for="({ x, s }, i) in aois" :key="x.id">
          <input v-model="x.label" class="aoi-name" list="aoi-labels" :aria-label="`Название зоны ${i + 1}`" />
          <span class="share num">{{ Math.round(s.share * 100) }}%</span>
          <span class="lift num" :class="liftTone(s.lift)">×{{ s.lift.toFixed(1) }}</span>
          <button
            class="btn ghost sm icon"
            title="Удалить зону"
            :aria-label="`Удалить зону «${x.label}»`"
            @click="remove(x.id)"
          >
            <X :size="14" />
          </button>
          <div class="aoi-bar">
            <i :style="{ width: `${s.share * 100}%` }" /><i class="area" :style="{ left: `${s.area * 100}%` }" />
          </div>
        </li>
      </ul>
      <datalist id="aoi-labels">
        <option v-for="l in AOI_LABELS" :key="l" :value="l" />
      </datalist>
      <p v-if="aois.length" class="aoi-help num">×2 — зона получает вдвое больше внимания, чем занимает места</p>
    </section>

    <section v-if="notes.length">
      <div class="sec-head"><span class="label">Что исправить</span></div>
      <ul class="notes">
        <li v-for="(n, i) in notes" :key="i" :class="n.level">
          <i class="dot" :class="n.level" />
          <div>
            <strong>{{ n.title }}</strong>
            <p>{{ n.text }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- сразу после выводов: «вот что не так» → «перерисовать с учётом этого» -->
    <ImprovePanel v-if="features.improve" :variant="variant" />

    <section>
      <div class="sec-head"><span class="label">Палитра</span></div>
      <div class="palette">
        <i
          v-for="c in a.palette"
          :key="c.hex"
          :style="{ background: c.hex, flexGrow: c.share }"
          :title="`${c.hex} · ${pct(c.share)}`"
        />
      </div>
    </section>

    <CritiquePanel :variant="variant" />
  </aside>
</template>

<style scoped>
.inspector {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 22px 22px 32px;
  border-left: 1px solid var(--line);
  background: var(--bg);
  min-height: 0;
}

.hero {
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
}

.big {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 6px;
}

.n {
  font-size: 76px;
  line-height: 0.95;
  font-weight: 300;
  letter-spacing: -0.05em;
}

.n.good {
  color: var(--ink);
}
.n.warn {
  color: var(--warn);
}
.n.bad {
  color: var(--bad);
}

.of {
  font-size: 15px;
  color: var(--ink-3);
}

.verdict {
  margin: 8px 0 4px;
  font-size: 15px;
  font-weight: 500;
}

.lead {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink-3);
}

.sec-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.metrics {
  display: grid;
  gap: 18px;
}

.empty-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.aois {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.aois li {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  align-items: center;
  gap: 8px;
}

.aoi-name {
  min-width: 0;
  height: 28px;
  padding: 0 8px;
  margin-left: -8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  font-size: 13.5px;
  font-weight: 500;
}

.aoi-name:hover,
.aoi-name:focus {
  border-color: var(--line);
  background: var(--panel);
  outline: none;
}

/* фокус с клавиатуры должен быть заметен, а не только лёгкая рамка */
.aoi-name:focus-visible {
  border-color: var(--ink-2);
}

.share {
  font-size: 14px;
  font-weight: 600;
}

.lift {
  font-size: 12px;
  color: var(--ink-3);
  min-width: 36px;
  text-align: right;
}

.lift.good {
  color: var(--good);
}
.lift.bad {
  color: var(--bad);
}

.aoi-bar {
  grid-column: 1 / -1;
  position: relative;
  height: 4px;
  border-radius: 2px;
  background: var(--panel-2);
}

.aoi-bar i {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 2px;
  background: var(--ink);
}

.aoi-bar i.area {
  inset: -3px auto -3px auto;
  width: 1.5px;
  background: var(--accent);
}

.aoi-help {
  margin: 10px 0 0;
  font-size: 10.5px;
  color: var(--ink-3);
}

.notes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 14px;
}

.notes li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
}

.notes .dot {
  margin-top: 6px;
}

.notes strong {
  font-size: 13.5px;
  font-weight: 600;
}

.notes p {
  margin: 2px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.palette {
  display: flex;
  height: 26px;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ink) 10%, transparent);
}

.palette i {
  flex-basis: 0;
}
</style>
