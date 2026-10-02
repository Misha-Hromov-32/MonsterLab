<script setup lang="ts">
import '@fontsource-variable/montserrat'
import { computed } from 'vue'
import {
  ArrowDown,
  FolderOpen,
  Layers,
  LayoutPanelTop,
  ScanEye,
  Search,
  Sparkles,
  Upload,
  Users,
} from 'lucide-vue-next'
import BeforeAfter from './BeforeAfter.vue'
import ExamplesGallery from './ExamplesGallery.vue'
import BrandMark from '../BrandMark.vue'
import { addFiles, site } from '../../store'
import { useFilePicker } from '../../lib/useFilePicker'
import type { Landing } from '../../lib/types'

// «Бренд» — главная в стиле логотипа: жирные прописные как на штампе MON STORE LAB, квадратная рамка,
// знак «O с рожками» и маджента. Цвет бренда — на кнопках, рамке и одной ленте; остальное — белый,
// розоватые оттенки и тёмно-сливовый, чтобы маджента не рябила.
const props = defineProps<{ l: Landing }>()

// тире в конце заголовка («Куда посмотрит покупатель —») в крупном наборе уезжает на отдельную строку
const title = computed(() => props.l.title.replace(/\s*[—–-]\s*$/, ''))

const pick = useFilePicker((files) => addFiles(files))

const card = computed(() => site.showcase?.card)
const feed = computed(() => site.showcase?.feed)
const bars = computed(() => {
  const s = card.value?.scores
  return s
    ? [
        { t: 'Фокус', v: s.focus },
        { t: 'Лёгкость', v: s.ease },
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

const TICKER = [
  'Карта внимания',
  'Слепые зоны WB',
  'Тест полки',
  'Разбор арт-директора',
  'Выбор покупателя',
  'Конкуренты из выдачи',
  'Новая обложка',
]

const FEATURES = [
  {
    id: 'critique',
    icon: ScanEye,
    title: 'Разбор как у арт-директора',
    text: 'Стиль, сегмент и аудитория, роль каждой надписи, порядок чтения и вид рядом с конкурентами. Что сильное — оставить, что слабое — как исправить.',
  },
  {
    id: 'blind',
    icon: LayoutPanelTop,
    title: 'Слепые зоны WB',
    text: 'Покажем, что закроют бейджи, сердечко, скидка и корзина, — и как карточка выглядит с ними.',
  },
  {
    id: 'shelf',
    icon: Layers,
    title: 'Тест полки',
    text: 'Заметят ли обложку среди конкурентов на разных местах выдачи.',
  },
  { id: 'choice', icon: Users, title: 'Выбор покупателя', text: 'Какой из вариантов выберут чаще и почему.' },
  {
    id: 'rivals',
    icon: Search,
    title: 'Конкуренты из выдачи',
    text: 'Подберём обложки с Wildberries по вашему запросу.',
  },
  { id: 'improve', icon: Sparkles, title: 'Новая обложка', text: 'Перерисуем вариант с учётом замечаний разбора.' },
  {
    id: 'library',
    icon: FolderOpen,
    title: 'Личный кабинет',
    text: 'Все проверенные обложки и результаты — открыть, скачать, сравнить с новыми.',
  },
]
</script>

<template>
  <div class="brand">
    <!-- ---------------------------------------------------------------- первый экран -->
    <section class="hero">
      <div class="glow" aria-hidden="true" />
      <div class="copy rise">
        <span class="eyebrow"><BrandMark :size="15" /> {{ l.eyebrow }}</span>
        <h1 class="title">{{ title }}</h1>
        <p v-if="l.title_muted" class="title-2">{{ l.title_muted }}</p>
        <p class="lead">{{ l.lead }}</p>
        <div class="ctas">
          <button type="button" class="b-cta" @click="pick()">
            <Upload :size="18" aria-hidden="true" /> {{ l.cta }}
          </button>
          <a class="b-ghost" href="#examples">Смотреть примеры <ArrowDown :size="16" aria-hidden="true" /></a>
        </div>
        <span class="hint">или перетащите файлы прямо в окно · JPG, PNG, WebP</span>
      </div>

      <div class="stage rise">
        <!-- обложка в рамке, как буквы в квадрате логотипа; рожки знака выглядывают из-за рамки -->
        <div class="frame">
          <BrandMark class="horns" :size="64" />
          <div class="shot">
            <BeforeAfter v-if="card" :card="card" />
            <div v-else class="ph" />
          </div>
          <span class="drag">← потяните шторку →</span>
        </div>

        <div class="chip c-index">
          <span class="c-label">Индекс заметности</span>
          <div class="c-big">{{ card?.index ?? '—' }}<small>/100</small></div>
          <ul class="c-bars">
            <li v-for="b in bars" :key="b.t">
              <span>{{ b.t }}</span>
              <i><b :style="{ width: `${b.v}%` }" /></i>
            </li>
          </ul>
        </div>

        <div class="chip c-focus">
          <span class="c-label">Половина внимания</span>
          <div class="c-big">{{ card ? Math.round(card.area50 * 100) : '—' }}<small>% площади</small></div>
        </div>

        <div class="chip c-feed">
          <span class="c-label">В ленте среди конкурентов</span>
          <div class="c-big">{{ lift }}</div>
          <span class="c-sub">от средней заметности</span>
        </div>
      </div>
    </section>

    <!-- ---------------------------------------------------------------- лента с функциями -->
    <div class="ticker" aria-hidden="true">
      <div class="track">
        <template v-for="copy in 2" :key="copy">
          <span v-for="t in TICKER" :key="`${copy}-${t}`" class="t-item">
            {{ t }} <BrandMark class="t-mark" :size="22" />
          </span>
        </template>
      </div>
    </div>

    <!-- ---------------------------------------------------------------- как это работает -->
    <section id="how" class="block">
      <div class="head">
        <span class="kicker">Как это работает</span>
        <h2 class="h2">Три шага до сильной обложки</h2>
      </div>
      <ol class="steps">
        <li v-for="(s, i) in l.steps" :key="i">
          <span class="num">{{ String(i + 1).padStart(2, '0') }}</span>
          <h3>{{ s.title }}</h3>
          <p>{{ s.text }}</p>
        </li>
      </ol>
    </section>

    <!-- ---------------------------------------------------------------- возможности -->
    <section class="block" aria-labelledby="brand-features">
      <div class="head">
        <span class="kicker">Возможности</span>
        <h2 id="brand-features" class="h2">Всё, чтобы карточку заметили</h2>
      </div>
      <div class="bento">
        <article v-for="f in FEATURES" :key="f.id" class="tile" :class="f.id">
          <span class="t-icon"><component :is="f.icon" :size="22" aria-hidden="true" /></span>
          <h3>{{ f.title }}</h3>
          <p>{{ f.text }}</p>
          <!-- слепые зоны: схема углов карточки -->
          <div v-if="f.id === 'blind'" class="corners" aria-hidden="true">
            <i class="k-tl" /><i class="k-tr" /><i class="k-bl" /><i class="k-br" />
          </div>
          <BrandMark v-if="f.id === 'critique'" class="t-ghost" :size="180" />
        </article>
      </div>
    </section>

    <section class="block examples">
      <ExamplesGallery />
    </section>

    <!-- ---------------------------------------------------------------- финальный призыв -->
    <section class="final">
      <div class="final-copy">
        <h2>Проверьте обложку до того, как за неё заплатит реклама</h2>
        <p>Карта внимания, метрики и разбор — в одном окне. Начните с демо-доступа после регистрации.</p>
        <button type="button" class="b-cta on-dark" @click="pick()">
          <Upload :size="18" aria-hidden="true" /> {{ l.cta }}
        </button>
      </div>
      <BrandMark class="final-mark" :size="260" />
    </section>
  </div>
</template>

<style scoped>
/* ------------------------------------------------------------------ палитра бренда */
.brand {
  --display: 'Montserrat Variable', 'Montserrat', var(--font-sans);
  --plum: #1d0b1a; /* почти чёрный с оттенком логотипа: тёмные плитки и финальный блок */
  --on-brand: #ffffff;
  --b-soft: color-mix(in srgb, var(--brand) 6%, var(--bg));
  --b-soft-2: color-mix(in srgb, var(--brand) 13%, var(--bg));
  --b-line: color-mix(in srgb, var(--brand) 22%, var(--line));
  /* общие компоненты (галерея примеров) берут акцент отсюда */
  --lime: var(--brand);
  --on-tile: var(--on-brand);
  background: var(--bg);
  overflow-x: clip;
}

/* в тёмной теме маджента светлее — текст на ней тёмный, иначе не хватает контраста */
:global(:root[data-theme='dark'] .brand) {
  --plum: #2a0f26;
  --on-brand: #1d0b1a;
}

/* ------------------------------------------------------------------ первый экран */
.hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(32px, 5vw, 72px);
  max-width: 1360px;
  margin: 0 auto;
  padding: clamp(36px, 7vh, 88px) clamp(20px, 4vw, 56px) clamp(48px, 8vh, 96px);
}

.glow {
  position: absolute;
  inset: -10% -20% auto auto;
  width: 70%;
  height: 120%;
  background:
    radial-gradient(closest-side at 60% 40%, color-mix(in srgb, var(--brand) 18%, transparent), transparent),
    radial-gradient(closest-side at 30% 70%, color-mix(in srgb, var(--brand) 9%, transparent), transparent);
  filter: blur(20px);
  pointer-events: none;
  z-index: 0;
}

.copy,
.stage {
  position: relative;
  z-index: 1;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px 6px 10px;
  border: 1px solid var(--b-line);
  border-radius: 999px;
  background: var(--b-soft);
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
}

.title {
  margin: 22px 0 0;
  font-family: var(--display);
  font-weight: 900;
  font-size: clamp(40px, 5.4vw, 86px);
  line-height: 0.95;
  letter-spacing: -0.035em;
  text-transform: uppercase;
  text-wrap: balance;
}

.title-2 {
  margin: 14px 0 0;
  font-family: var(--display);
  font-weight: 700;
  font-size: clamp(22px, 2.3vw, 36px);
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: var(--brand);
  text-wrap: balance;
}

.lead {
  max-width: 520px;
  margin: 24px 0 32px;
  font-size: 18px;
  line-height: 1.5;
  letter-spacing: -0.015em;
  color: var(--ink-2);
}

.ctas {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.b-cta,
.b-ghost {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 54px;
  padding: 0 26px;
  border-radius: 14px;
  font-family: var(--display);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.01em;
  text-transform: uppercase;
  text-decoration: none;
  transition:
    transform 0.15s,
    box-shadow 0.2s,
    background 0.15s;
}

.b-cta {
  border: 0;
  background: var(--brand);
  color: var(--on-brand);
  box-shadow: 0 14px 30px -14px color-mix(in srgb, var(--brand) 80%, transparent);
}

.b-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 36px -16px color-mix(in srgb, var(--brand) 90%, transparent);
}

.b-cta:active {
  transform: translateY(0);
}

.b-ghost {
  border: 2px solid var(--ink);
  color: var(--ink);
  background: transparent;
}

.b-ghost:hover {
  background: var(--ink);
  color: var(--bg);
}

.hint {
  display: block;
  margin-top: 14px;
  font-size: 13px;
  color: var(--ink-3);
}

/* сцена: обложка в рамке и плавающие карточки с цифрами */
.stage {
  display: grid;
  place-items: center;
  min-height: 560px;
}

.frame {
  position: relative;
  width: min(100%, 360px);
  padding: 14px;
  border: 7px solid var(--brand);
  border-radius: 6px;
  background: var(--bg);
  box-shadow: 0 40px 80px -40px color-mix(in srgb, var(--brand) 55%, transparent);
}

/* рожки знака выглядывают из-за верхней рамки */
.horns {
  position: absolute;
  top: -50px;
  left: 50%;
  translate: -50% 0;
  clip-path: inset(0 0 52% 0);
  z-index: 0;
}

.shot {
  position: relative;
  z-index: 1;
}

.shot :deep(.ba) {
  border-radius: 2px;
}

.ph {
  aspect-ratio: 3 / 4;
  background: var(--b-soft-2);
  animation: pulse 1.4s ease-in-out infinite;
}

.drag {
  position: absolute;
  left: 50%;
  bottom: -38px;
  translate: -50% 0;
  white-space: nowrap;
  font-size: 12px;
  color: var(--ink-3);
}

.chip {
  position: absolute;
  z-index: 2;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: color-mix(in srgb, var(--panel) 88%, transparent);
  backdrop-filter: blur(12px);
  box-shadow: 0 18px 40px -20px rgba(29, 11, 26, 0.35);
  animation: float 7s ease-in-out infinite;
}

.c-label {
  display: block;
  font-size: 12px;
  color: var(--ink-2);
}

.c-big {
  margin-top: 4px;
  font-family: var(--display);
  font-weight: 900;
  font-size: 40px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.c-big small {
  margin-left: 4px;
  font-family: var(--font-sans);
  font-weight: 500;
  font-size: 13px;
  letter-spacing: 0;
  color: var(--ink-3);
}

.c-sub {
  font-size: 12px;
  color: color-mix(in srgb, currentColor 70%, transparent);
}

.c-index {
  top: 4%;
  left: -2%;
  width: 184px;
}

.c-bars {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.c-bars li {
  display: grid;
  grid-template-columns: 62px 1fr;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--ink-2);
}

.c-bars i {
  height: 5px;
  border-radius: 3px;
  background: var(--b-soft-2);
  overflow: hidden;
}

.c-bars b {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--brand);
}

.c-focus {
  right: -2%;
  top: 24%;
  animation-delay: -2.5s;
}

.c-feed {
  right: 4%;
  bottom: 8%;
  border-color: transparent;
  background: var(--plum);
  color: #fff;
  animation-delay: -5s;
}

.c-feed .c-label {
  color: rgba(255, 255, 255, 0.7);
}

.c-feed .c-big {
  color: #ff8af0;
}

@keyframes float {
  0%,
  100% {
    translate: 0 0;
  }
  50% {
    translate: 0 -8px;
  }
}

/* ------------------------------------------------------------------ бегущая лента */
.ticker {
  overflow: hidden;
  padding: 18px 0;
  background: var(--brand);
  color: var(--on-brand);
  rotate: -1.2deg;
  margin: 0 -2%;
}

.track {
  display: flex;
  width: max-content;
  animation: ticker 40s linear infinite;
}

.t-item {
  display: inline-flex;
  align-items: center;
  gap: 28px;
  padding-right: 28px;
  font-family: var(--display);
  font-weight: 900;
  font-size: clamp(20px, 2vw, 28px);
  letter-spacing: -0.01em;
  text-transform: uppercase;
  white-space: nowrap;
}

.t-mark {
  fill: var(--on-brand);
}

@keyframes ticker {
  to {
    translate: -50% 0;
  }
}

/* ------------------------------------------------------------------ секции */
.block {
  max-width: 1360px;
  margin: 0 auto;
  padding: clamp(56px, 9vh, 104px) clamp(20px, 4vw, 56px) 0;
}

#how {
  scroll-margin-top: 24px;
}

.head {
  max-width: 760px;
  margin-bottom: 32px;
}

.kicker {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand);
}

.h2 {
  margin: 10px 0 0;
  font-family: var(--display);
  font-weight: 900;
  font-size: clamp(30px, 3.6vw, 54px);
  line-height: 1;
  letter-spacing: -0.035em;
  text-transform: uppercase;
  text-wrap: balance;
}

/* шаги: крупные контурные номера, как цифры на штампе */
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.steps li {
  position: relative;
  padding: 26px 26px 30px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--panel);
  transition:
    border-color 0.2s,
    transform 0.2s;
}

.steps li:hover {
  border-color: var(--b-line);
  transform: translateY(-3px);
}

.num {
  display: block;
  font-family: var(--display);
  font-weight: 900;
  font-size: 56px;
  line-height: 0.9;
  letter-spacing: -0.05em;
  color: var(--brand);
}

.steps h3 {
  margin: 22px 0 8px;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.steps p,
.tile p {
  margin: 0;
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink-2);
}

/* возможности: бенто-сетка 4 × 3 */
.bento {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: minmax(190px, auto);
  gap: 16px;
}

.tile {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--panel);
  overflow: hidden;
  transition:
    transform 0.2s,
    border-color 0.2s;
}

.tile:hover {
  transform: translateY(-3px);
  border-color: var(--b-line);
}

.t-icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: var(--b-soft-2);
  color: var(--brand);
}

.tile h3 {
  margin: 18px 0 8px;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.critique {
  grid-column: span 2;
  grid-row: span 2;
  justify-content: flex-end;
  border-color: transparent;
  background: var(--plum);
  color: #fff;
}

.critique h3 {
  font-family: var(--display);
  font-weight: 900;
  font-size: clamp(26px, 2.6vw, 40px);
  line-height: 1;
  letter-spacing: -0.035em;
  text-transform: uppercase;
}

.critique p {
  max-width: 440px;
  color: rgba(255, 255, 255, 0.72);
}

.critique .t-icon {
  position: absolute;
  top: 24px;
  left: 24px;
  background: rgba(255, 255, 255, 0.1);
  color: #ff8af0;
}

.t-ghost {
  position: absolute;
  top: 18px;
  right: -24px;
  fill: color-mix(in srgb, var(--brand) 35%, transparent) !important;
  rotate: 12deg;
}

.blind {
  grid-column: span 2;
  border-color: transparent;
  background: var(--brand);
  color: var(--on-brand);
  padding-right: 180px;
}

.blind p {
  color: color-mix(in srgb, var(--on-brand) 82%, transparent);
}

.blind .t-icon {
  background: color-mix(in srgb, var(--on-brand) 18%, transparent);
  color: var(--on-brand);
}

/* схема карточки с углами — как в режиме «Слепые зоны» */
.corners {
  position: absolute;
  right: 28px;
  top: 50%;
  translate: 0 -50%;
  width: 110px;
  aspect-ratio: 3 / 4;
  border-radius: 10px;
  background: color-mix(in srgb, var(--on-brand) 92%, transparent);
  rotate: 6deg;
  box-shadow: 0 20px 40px -20px rgba(0, 0, 0, 0.5);
}

.corners i {
  position: absolute;
  border-radius: 4px;
}

.k-tl {
  left: 6px;
  top: 6px;
  width: 30px;
  height: 14px;
  background: #1db67b;
}

.k-tr {
  right: 6px;
  top: 6px;
  width: 16px;
  height: 16px;
  border-radius: 50% !important;
  border: 2px solid #1c1c1c;
}

.k-bl {
  left: 6px;
  bottom: 8px;
  width: 52px;
  height: 26px;
  background: linear-gradient(#f5157d 0 33%, #ff6a1a 33% 66%, #f7d41a 66%);
}

.k-br {
  right: 6px;
  bottom: 8px;
  width: 20px;
  height: 20px;
  border-radius: 50% !important;
  background: #cb11ab;
}

.library {
  grid-column: span 2;
  background: var(--b-soft);
  border-color: var(--b-line);
}

.examples {
  --line: var(--b-line);
}

/* заголовок галереи — тем же жирным набором, что и остальные секции */
.examples :deep(.head h2) {
  font-family: var(--display);
  font-weight: 900;
  font-size: clamp(30px, 3.6vw, 54px);
  line-height: 1;
  letter-spacing: -0.035em;
  text-transform: uppercase;
}

/* ------------------------------------------------------------------ финал */
.final {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 32px;
  max-width: 1360px;
  margin: clamp(64px, 10vh, 112px) auto clamp(40px, 6vh, 72px);
  padding: clamp(36px, 6vw, 72px);
  border-radius: 28px;
  background: var(--plum);
  color: #fff;
  overflow: hidden;
  width: calc(100% - 2 * clamp(20px, 4vw, 56px));
}

.final h2 {
  margin: 0;
  max-width: 760px;
  font-family: var(--display);
  font-weight: 900;
  font-size: clamp(30px, 4vw, 60px);
  line-height: 0.98;
  letter-spacing: -0.035em;
  text-transform: uppercase;
  text-wrap: balance;
}

.final p {
  max-width: 560px;
  margin: 18px 0 30px;
  font-size: 17px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.72);
}

.final-mark {
  fill: var(--brand) !important;
  opacity: 0.9;
  rotate: -8deg;
}

/* ------------------------------------------------------------------ адаптив и движение */
@media (max-width: 1080px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .stage {
    min-height: 520px;
  }
  .bento {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .steps {
    grid-template-columns: 1fr;
  }
  .final {
    grid-template-columns: 1fr;
  }
  .final-mark {
    display: none;
  }
}

@media (max-width: 560px) {
  .stage {
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 40px;
  }
  .chip {
    position: static;
    width: 100%;
    animation: none;
  }
  .frame {
    margin-bottom: 40px;
  }
  .bento {
    grid-template-columns: 1fr;
  }
  .critique,
  .blind,
  .library {
    grid-column: auto;
    grid-row: auto;
  }
  .critique {
    min-height: 320px;
  }
  .blind {
    padding-right: 24px;
  }
  .corners {
    display: none;
  }
  .b-cta,
  .b-ghost {
    width: 100%;
    justify-content: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chip,
  .track {
    animation: none;
  }
}
</style>
