<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import UploadButton from './UploadButton.vue'
import ExamplesGallery from './ExamplesGallery.vue'
import Steps from './Steps.vue'
import { bgRgb, drawOverlay } from '../../lib/heat'
import { pct } from '../../lib/format'
import { site } from '../../store'
import type { Landing, Showcase } from '../../lib/types'

defineProps<{ l: Landing }>()

const stage = ref<HTMLDivElement>()
const fog = ref<HTMLCanvasElement>()
const light = ref({ x: -999, y: -999, on: false })
let ro: ResizeObserver | undefined

function redraw() {
  const el = stage.value,
    c = fog.value,
    feed = site.showcase?.feed
  if (!el || !c || !feed) return
  const r = el.getBoundingClientRect()
  // цвет тумана = фон страницы (feed-dark включает тёмную палитру), чтобы лента растворялась в ней
  drawOverlay(c, feed.grid, 'fog', r.width, r.height, 0.95, bgRgb())
}

function move(e: PointerEvent) {
  const r = stage.value!.getBoundingClientRect()
  light.value = { x: e.clientX - r.left, y: e.clientY - r.top, on: true }
}

onMounted(() => {
  ro = new ResizeObserver(redraw)
  // этот вариант главной всегда тёмный: класс включает тёмную палитру из base.css для всей страницы, включая шапку
  document.documentElement.classList.add('feed-dark')
})
onUnmounted(() => {
  ro?.disconnect()
  document.documentElement.classList.remove('feed-dark')
})
// сцена появляется, когда пришла витрина — тогда и подписываемся на размер
watch(stage, (el, old) => {
  if (old) ro?.unobserve(old)
  if (el) ro?.observe(el)
})
watch(
  () => site.showcase,
  () => nextTick(redraw),
)

type Tile = Showcase['feed']['tiles'][number]
// сотые доли процента: плитки должны совпасть с картой тумана, нарисованной по тем же координатам
const box = (t: Tile) => ({ left: pct(t.x, 2), top: pct(t.y, 2), width: pct(t.w, 2), height: pct(t.h, 2) })

// индекс «своей» карточки приходит с сервера — без проверки границ рамка упала бы на undefined
const targetTile = computed(() => {
  const feed = site.showcase?.feed
  return feed ? (feed.tiles[feed.target] ?? null) : null
})
</script>

<template>
  <div class="feedland">
    <section class="hero">
      <div
        v-if="site.showcase"
        ref="stage"
        class="stage"
        :style="{
          aspectRatio: `${site.showcase.feed.width} / ${site.showcase.feed.height}`,
          '--mx': `${light.x}px`,
          '--my': `${light.y}px`,
        }"
        @pointermove="move"
        @pointerleave="light.on = false"
      >
        <img v-for="(t, i) in site.showcase.feed.tiles" :key="i" :src="t.url" alt="" class="tile" :style="box(t)" />
        <canvas ref="fog" class="fog" :class="{ lit: light.on }" />
        <div v-if="targetTile" class="target" :style="box(targetTile)">
          <span class="num"> Ваша карточка · {{ pct(site.showcase.feed.share) }} внимания ленты </span>
        </div>
        <div class="fade" />
      </div>
      <div v-else class="stage placeholder" />

      <div class="copy rise">
        <span class="label">{{ l.eyebrow }}</span>
        <h1>
          {{ l.title }}
          <em v-if="l.title_muted">{{ l.title_muted }}</em>
        </h1>
        <div class="row">
          <p class="lead">{{ l.lead }}</p>
          <div class="cta">
            <UploadButton :label="l.cta" tone="accent" />
            <span class="note num">Туман — то, что покупатель пропустит. Водите курсором по ленте.</span>
          </div>
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
/* тёмная палитра приходит из base.css через класс feed-dark на <html> */
.feedland {
  flex: 1;
  overflow-y: auto;
  background: var(--bg);
  color: var(--ink);
}

.hero {
  position: relative;
}

.stage {
  position: relative;
  width: 100%;
  overflow: hidden;
  cursor: crosshair;
  background: var(--bg);
}

.placeholder {
  aspect-ratio: 2.3 / 1;
  animation: pulse 1.4s ease-in-out infinite;
}

.tile {
  position: absolute;
  object-fit: cover;
  border-radius: 10px;
}

.fog {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.fog.lit {
  -webkit-mask-image: radial-gradient(circle 150px at var(--mx) var(--my), transparent 0, transparent 40%, #000 100%);
  mask-image: radial-gradient(circle 150px at var(--mx) var(--my), transparent 0, transparent 40%, #000 100%);
}

.target {
  position: absolute;
  border-radius: 10px;
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  pointer-events: none;
}

.target span {
  position: absolute;
  left: 50%;
  bottom: 10px;
  transform: translateX(-50%);
  padding: 5px 10px;
  border-radius: 6px;
  background: var(--accent);
  color: var(--on-accent);
  font-size: 11px;
  white-space: nowrap;
}

.fade {
  position: absolute;
  inset: auto 0 0 0;
  height: 45%;
  background: linear-gradient(to bottom, transparent, var(--bg));
  pointer-events: none;
}

.copy {
  position: relative;
  max-width: 1280px;
  margin: -140px auto 0;
  padding: 0 clamp(20px, 5vw, 64px);
}

h1 {
  margin: 12px 0 24px;
  max-width: 1000px;
  font-size: clamp(34px, 5vw, 72px);
  line-height: 1;
  font-weight: 300;
  letter-spacing: -0.04em;
}

h1 em {
  display: block;
  font-style: normal;
  color: var(--ink-3);
}

.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 48px;
  align-items: start;
}

.lead {
  max-width: 560px;
  margin: 0;
  font-size: 17px;
  line-height: 1.55;
  color: var(--ink-2);
}

.cta {
  display: grid;
  gap: 12px;
  justify-items: start;
}

.note {
  font-size: 11px;
  color: var(--ink-3);
}

.below {
  display: grid;
  gap: 48px;
  max-width: 1280px;
  margin: 0 auto;
  padding: 64px clamp(20px, 5vw, 64px);
}

@media (max-width: 900px) {
  .copy {
    margin-top: -40px;
  }
  .row {
    grid-template-columns: 1fr;
    gap: 24px;
  }
}
</style>
