<script setup lang="ts">
import { computed } from 'vue'
import { Upload } from 'lucide-vue-next'
import BeforeAfter from './BeforeAfter.vue'
import ExamplesGallery from './ExamplesGallery.vue'
import Steps from './Steps.vue'
import { addFiles, featuredExample, loadExample, site } from '../../store'
import { useFilePicker } from '../../lib/useFilePicker'
import type { Landing } from '../../lib/types'

defineProps<{ l: Landing }>()

// своя кнопка, а не UploadButton: здесь она в паре с «Открыть пример» и в другом размере
const pick = useFilePicker((files) => addFiles(files))

const card = computed(() => site.showcase?.card)
const feed = computed(() => site.showcase?.feed)
const bars = computed(() => {
  const s = card.value?.scores
  return s
    ? [
        { t: 'Фокус', v: s.focus },
        { t: 'Ясность', v: s.clarity },
        { t: 'Превью', v: s.thumb },
        { t: 'Контраст', v: s.contrast },
      ]
    : []
})

// во сколько раз карточка заметнее средней в ленте; проверка > 0 — страховка от битого ответа сервера
const lift = computed(() => {
  const f = feed.value
  return f && f.fair > 0 ? `×${(f.share / f.fair).toFixed(1)}` : '—'
})

const ORDER_LABELS = ['сначала сюда', 'затем', 'потом']

/** Декоративный график на лаймовой плитке — не данные, а ритм; высоты в % от плитки. */
const SPARK = [55, 22, 59, 26, 63, 30, 67, 34, 71, 38, 75, 42]
</script>

<template>
  <div class="split">
    <section class="hero">
      <div class="copy rise">
        <span class="label">{{ l.eyebrow }}</span>
        <h1 class="display">
          {{ l.title }}
          <span v-if="l.title_muted" class="muted">{{ l.title_muted }}</span>
        </h1>
        <p class="lead">{{ l.lead }}</p>
        <div class="ctas">
          <button v-if="featuredExample" type="button" class="btn pill cta" @click="loadExample(featuredExample)">
            Открыть пример
          </button>
          <button type="button" class="btn primary cta" @click="pick()">
            <Upload :size="16" aria-hidden="true" /> {{ l.cta }}
          </button>
        </div>
        <span class="hint">или перетащите файлы прямо в окно</span>
      </div>

      <div class="collage">
        <!-- голубая плитка с обложкой и шторкой -->
        <div class="tile sky big">
          <div class="inner">
            <BeforeAfter v-if="card" :card="card" />
            <div v-else class="ph" />
          </div>
          <span class="cap">Потяните шторку</span>
        </div>

        <!-- белая карточка с индексом в стиле интерфейса продукта -->
        <div class="ui-card">
          <span class="ui-label">Индекс заметности</span>
          <div class="ui-num display">{{ card?.index ?? '—' }}<small>/100</small></div>
          <ul class="ui-bars">
            <li v-for="b in bars" :key="b.t">
              <span>{{ b.t }}</span>
              <i><b :style="{ width: `${b.v}%` }" /></i>
            </li>
          </ul>
        </div>

        <!-- лаймовая плитка с главной цифрой -->
        <div class="tile lime stat">
          <span class="ui-label dark">Половина внимания</span>
          <div class="stat-num display">{{ card ? Math.round(card.area50 * 100) : '—' }}%</div>
          <span class="stat-sub">площади обложки</span>
          <div class="spark" aria-hidden="true">
            <i v-for="(h, n) in SPARK" :key="n" :style="{ height: `${h}%` }" />
          </div>
        </div>

        <!-- сиреневая плитка: порядок взгляда -->
        <div class="tile lilac order">
          <span class="ui-label dark">Порядок взгляда</span>
          <ol>
            <li v-for="(f, i) in card?.fixations.slice(0, 3) ?? []" :key="i">
              <b>{{ i + 1 }}</b>
              <span>{{ ORDER_LABELS[i] }} · {{ Math.round(f.mass * 100) }}%</span>
            </li>
          </ol>
        </div>

        <!-- мятная плитка: лента -->
        <div class="tile mint shelf">
          <span class="ui-label dark">В ленте среди конкурентов</span>
          <div class="stat-num display sm">{{ lift }}</div>
          <span class="stat-sub">от средней заметности</span>
        </div>
      </div>
    </section>

    <div class="below">
      <Steps :steps="l.steps" />
      <ExamplesGallery />
    </div>
  </div>
</template>

<style scoped>
.split {
  flex: 1;
  overflow-y: auto;
  background: var(--bg);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(32px, 5vw, 80px);
  max-width: 1360px;
  margin: 0 auto;
  padding: clamp(28px, 6vh, 72px) clamp(20px, 4vw, 56px) 48px;
}

h1 {
  margin: 16px 0 22px;
  font-size: clamp(40px, 4.4vw, 66px);
}

h1 .muted {
  display: block;
  color: var(--ink-3);
}

.lead {
  max-width: 520px;
  margin: 0 0 30px;
  font-size: 19px;
  font-weight: 300;
  line-height: 1.4;
  letter-spacing: -0.02em;
  color: var(--ink-2);
}

.ctas {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.cta {
  height: 44px;
  padding: 0 18px;
  font-size: 15px;
  letter-spacing: -0.02em;
}

.hint {
  display: block;
  margin-top: 12px;
  font-size: 13px;
  color: var(--ink-3);
}

/* коллаж */
.collage {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 12px;
}

.tile {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  color: var(--on-tile);
}

.sky {
  background: var(--sky);
  background-image: radial-gradient(rgba(255, 255, 255, 0.28) 1.2px, transparent 1.2px);
  background-size: 14px 14px;
}
.lime {
  background: var(--lime);
}
.lilac {
  background: var(--lilac);
}
.mint {
  background: var(--mint);
}

.big {
  grid-row: span 2;
  display: grid;
  place-items: center;
  padding: 28px 30px 40px;
}

.big .inner {
  width: min(100%, 330px);
}

.big .inner :deep(.ba) {
  border-radius: 8px;
  box-shadow: 0 24px 60px -24px rgba(0, 0, 0, 0.5);
}

.ph {
  aspect-ratio: 3 / 4;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.4);
  animation: pulse 1.4s ease-in-out infinite;
}

.cap {
  position: absolute;
  left: 14px;
  bottom: 12px;
  font-size: 12px;
  color: var(--on-tile);
}

.ui-card {
  padding: 18px 18px 16px;
  border-radius: 10px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.ui-label {
  display: block;
  font-size: 13px;
  color: var(--ink-2);
}

.ui-label.dark {
  color: color-mix(in srgb, var(--on-tile) 70%, transparent);
}

.ui-num {
  margin: 4px 0 14px;
  font-size: 56px;
  line-height: 1;
}

.ui-num small {
  font-size: 16px;
  letter-spacing: 0;
  color: var(--ink-3);
}

.ui-bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.ui-bars li {
  display: grid;
  grid-template-columns: 70px 1fr;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--ink-2);
}

.ui-bars i {
  height: 6px;
  border-radius: 3px;
  background: var(--panel-2);
  overflow: hidden;
}

.ui-bars b {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--ink);
}

.stat {
  padding: 16px 18px 0;
  display: grid;
}

.stat-num {
  margin-top: 4px;
  font-size: 64px;
  line-height: 1;
}

.stat-num.sm {
  font-size: 48px;
}

.stat-sub {
  font-size: 13px;
  color: color-mix(in srgb, var(--on-tile) 65%, transparent);
}

.spark {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 46px;
  margin-top: 12px;
}

.spark i {
  flex: 1;
  border-radius: 3px 3px 0 0;
  background: color-mix(in srgb, var(--on-tile) 85%, transparent);
}

.order,
.shelf {
  padding: 16px 18px 18px;
}

.order ol {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.order li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13.5px;
}

.order b {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff;
  font-size: 12px;
  font-weight: 600;
}

.order li:first-child b {
  background: var(--on-tile);
  color: var(--lime);
}

.below {
  display: grid;
  gap: 56px;
  max-width: 1360px;
  margin: 0 auto;
  padding: 32px clamp(20px, 4vw, 56px) 72px;
}

@media (max-width: 1000px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .big {
    grid-column: 1 / -1;
    grid-row: auto;
  }
}

@media (max-width: 560px) {
  .collage {
    grid-template-columns: 1fr;
  }
}
</style>
